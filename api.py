from functools import wraps
from flask import Flask, jsonify, send_from_directory, request, abort
from database import get_connection, init_db, get_dishes, get_user_role, add_order, get_new_orders, update_order_status, validate_promo, use_promo, get_all_promocodes, create_promo, add_user, set_user_role_by_username
from config import WEB_APP_URL, CRYPTOBOT_TOKEN, BOT_TOKEN, ADMIN_TELEGRAM_ID, PORT, DEBUG
from werkzeug.utils import secure_filename
import os, json
import logging
import requests
import hmac
import hashlib
from datetime import datetime
from aiogram import Bot

# config
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__, static_folder='web_app', static_url_path='/web_app')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Настройка логирования
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

init_db()

# Crypto Pay API endpoint (оставляем для будущего, но не используем)
CRYPTO_PAY_API_URL = "https://pay.crypto.bot/createInvoice"

# Инициализация бота для уведомлений (только для доступа к токену, уведомления через bot.py)
bot = Bot(token=BOT_TOKEN)


def _is_admin_request(req: request) -> bool:
    if not ADMIN_TELEGRAM_ID:
        return False
    telegram_id = (
        req.headers.get("X-Telegram-Id")
        or req.args.get("telegram_id")
        or (req.json.get("telegram_id") if req.is_json else None)
    )
    return telegram_id and str(telegram_id) == str(ADMIN_TELEGRAM_ID)


def require_env_admin(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not _is_admin_request(request):
            return jsonify({"status": "error", "error": "admin access required"}), 403
        return func(*args, **kwargs)

    return wrapper


@app.route("/api/admin/config", methods=["GET"])
def admin_config():
    """Публичный конфиг для фронта (ID администратора)."""
    return jsonify({"admin_id": ADMIN_TELEGRAM_ID})

@app.route('/api/dishes', methods=['GET', 'POST'])
def api_dishes():
    if request.method == 'GET':
        cat = request.args.get('category')
        dishes = get_dishes(cat)
        return jsonify(dishes)

    # POST: add dish with multipart/form-data (image optional)
    if request.method == 'POST':
        if not _is_admin_request(request):
            return jsonify({"status": "error", "error": "admin access required"}), 403
        name = request.form.get('name')
        price = request.form.get('price')
        description = request.form.get('description', '')
        category = request.form.get('category', 'other')

        if not name or not price:
            return jsonify({"status": "error", "error": "name and price required"}), 400
        try:
            price_val = float(price)
        except:
            return jsonify({"status": "error", "error": "price must be numeric"}), 400

        image = request.files.get('image')
        image_path = ''
        if image and image.filename:
            filename = secure_filename(image.filename)
            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
            if ext not in ALLOWED_EXT:
                return jsonify({"status": "error", "error": "invalid image extension"}), 400
            base, ext = os.path.splitext(filename)
            fname = f"{base}_{int(os.times().system)}{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
            image.save(filepath)
            image_path = f"/uploads/{fname}"

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dishes (name, price, description, image_url, category)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, price_val, description, image_path, category))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "success"})

@app.route('/api/dishes/<int:dish_id>', methods=['DELETE'])
def api_dish_delete(dish_id):
    if not _is_admin_request(request):
        return jsonify({"status": "error", "error": "admin access required"}), 403
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT image_url FROM dishes WHERE id = %s", (dish_id,))
    r = cursor.fetchone()
    if r and r[0]:
        img_path = r[0]
        if img_path.startswith('/uploads/'):
            fs_path = img_path.lstrip('/')
            if os.path.exists(fs_path):
                try:
                    os.remove(fs_path)
                except Exception as e:
                    app.logger.warning(f"Failed to remove file {fs_path}: {e}")
    cursor.execute("DELETE FROM dishes WHERE id = %s", (dish_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/user/<int:telegram_id>', methods=['GET'])
def api_user(telegram_id):
    role = get_user_role(telegram_id)
    return jsonify({"telegram_id": telegram_id, "role": role})

@app.route('/api/add_admin', methods=['POST'])
def add_admin():
    if not _is_admin_request(request):
        return jsonify({"status": "error", "error": "admin access required"}), 403
    data = request.json or {}
    username = data.get('username')
    if not username:
        return jsonify({"status": "error", "error": "username is required"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE role = 'admin' LIMIT 1")
    existing_admin = cursor.fetchone()
    if existing_admin:
        cursor.close()
        conn.close()
        return jsonify({"status": "error", "error": "Админ уже существует"}), 400

    add_user(None, 'admin', username)
    set_user_role_by_username(username, 'admin')
    cursor.close()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/create_payment', methods=['POST'])
def create_payment():
    data = request.json or {}
    payment_data = data.get('payment', {})
    order_data = data.get('orderData', {})

    amount_fiat = payment_data.get('amount')  # Сумма в BYN
    order_id = payment_data.get('order_id', str(int(datetime.now().timestamp())))
    description = payment_data.get('description', 'Заказ в La Tavola')
    user_id = order_data.get('user', {}).get('id', 0)
    dishes = json.dumps(order_data.get('dishes', []))
    address = order_data.get('address', '')
    total = float(order_data.get('total', 0.0))  # Получаем total из orderData
    order_type = order_data.get('orderType', 'delivery')  # Получаем orderType из orderData

    if not amount_fiat or not order_id or not dishes or not address or not total:
        return jsonify({"status": "error", "error": "amount, order_id, dishes, address, and total are required"}), 400

    try:
        amount_fiat = float(amount_fiat)
    except (ValueError, TypeError):
        return jsonify({"status": "error", "error": "amount must be a valid number"}), 400

    # Заглушка: эмуляция успешного ответа от Crypto Pay
    app.logger.info(f"Processing payment (stub) with payload: {data}")
    response = {
        'status': 'success',
        'payment_url': f'https://example.com/pay/{order_id}',  # Фиктивный URL
        'invoice_id': f'invoice_{order_id}'
    }
    app.logger.info(f"Crypto Pay API response (stub): {response}")

    # Сохраняем заказ в базе данных
    order_id = add_order(user_id, dishes, address, total, order_type, payment_provider='stub_payment', payment_id=response['invoice_id'])
    if order_id:
        app.logger.info(f"Order {order_id} created successfully")
    else:
        return jsonify({"status": "error", "error": "Failed to create order"}), 500

    return jsonify(response), 200

@app.route('/api/callback', methods=['POST'])
def crypto_callback():
    data = request.get_json()
    app.logger.info(f"Received callback (stub): {data}")

    # Проверка подписи (для совместимости, но без реальной проверки)
    signature = request.headers.get('crypto-pay-api-signature')
    if signature:
        app.logger.info("Signature received, skipping validation in stub mode")
    else:
        app.logger.info("No signature in callback, proceeding in stub mode")

    if not data or 'update_type' not in data or data['update_type'] != 'invoice_paid':
        app.logger.warning("Invalid callback data (stub mode)")
        return jsonify({"status": "error", "error": "Invalid callback data"}), 400

    invoice = data.get('payload')
    if not invoice or 'invoice_id' not in invoice or 'status' not in invoice:
        app.logger.warning("Missing invoice details (stub mode)")
        return jsonify({"status": "error", "error": "Missing invoice details"}), 400

    invoice_id = invoice['invoice_id']
    status = invoice['status']

    if status == 'paid':
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET status = 'paid' WHERE payment_id = %s", (invoice_id,))
        if cursor.rowcount > 0:
            # Получаем user_id из заказа для уведомления (записываем в лог, уведомление через bot.py)
            cursor.execute("SELECT user_id FROM orders WHERE payment_id = %s", (invoice_id,))
            user_id = cursor.fetchone()
            if user_id:
                app.logger.info(f"Order {invoice_id} marked as paid (stub), user {user_id[0]} should be notified via bot.py")
            else:
                app.logger.warning(f"No user_id found for invoice_id: {invoice_id}")
        else:
            app.logger.warning(f"No order found for invoice_id: {invoice_id}")
        conn.commit()
        cursor.close()
        conn.close()
        app.logger.info(f"Order {invoice_id} marked as paid (stub)")
        return jsonify({"status": "success"})
    else:
        app.logger.warning(f"Order {invoice_id} status: {status} (stub)")
        return jsonify({"status": "pending"})

@app.route('/api/promotions', methods=['GET', 'POST', 'DELETE'])
def api_promotions():
    conn = get_connection()
    cursor = conn.cursor()
    if request.method == 'GET':
        cursor.execute("SELECT id, text, image_url FROM promotions")
        rows = cursor.fetchall()
        promotions = [{'id': r[0], 'text': r[1], 'image_url': r[2]} for r in rows]
        cursor.close()
        conn.close()
        return jsonify(promotions)
    elif request.method == 'POST':
        if not _is_admin_request(request):
            return jsonify({"status": "error", "error": "admin access required"}), 403
        data = request.json
        cursor.execute("INSERT INTO promotions (text, image_url) VALUES (%s, %s)", (data.get('text'), data.get('image_url', '')))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "success"})
    elif request.method == 'DELETE':
        if not _is_admin_request(request):
            return jsonify({"status": "error", "error": "admin access required"}), 403
        data = request.json
        cursor.execute("DELETE FROM promotions WHERE id = %s", (data.get('id'),))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "success"})

@app.route('/api/user/<int:telegram_id>/orders', methods=['GET'])
def api_user_orders(telegram_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, created_at, total, status FROM orders WHERE user_id = %s", (telegram_id,))
    rows = cursor.fetchall()
    orders = [
        {
            'id': r[0],
            'created_at': r[1].isoformat() if r[1] else None,
            'total': float(r[2]) if r[2] is not None else 0.0,
            'status': r[3] if r[3] else 'unknown'
        } for r in rows
    ]
    cursor.close()
    conn.close()
    return jsonify(orders)

@app.route('/api/validate_promo', methods=['POST'])
def validate_promo_api():
    data = request.json or {}
    code = data.get('code', '')
    app.logger.info(f"Validating promo code: {code}")
    result = validate_promo(code)
    if result['valid']:
        app.logger.info(f"Promo code {code} is valid, attempting to use")
        if use_promo(code):
            app.logger.info(f"Promo code {code} applied successfully")
            return jsonify({'status': 'success', 'valid': True, 'discount': result['discount']})
        else:
            app.logger.warning(f"Failed to use promo code {code}")
            return jsonify({'status': "error", "error": 'Не удалось применить промокод'}), 400
    app.logger.warning(f"Invalid promo code: {code}")
    return jsonify({'status': "error", 'valid': False, "error": 'Неверный или истёкший промокод'}), 400

@app.route('/api/promocodes', methods=['GET', 'POST', 'DELETE'])
def api_promocodes():
    conn = get_connection()
    cursor = conn.cursor()
    if request.method == 'GET':
        promocodes = get_all_promocodes()
        return jsonify(promocodes)
    elif request.method == 'POST':
        if not _is_admin_request(request):
            return jsonify({'status': 'error', 'error': 'admin access required'}), 403
        data = request.json
        code = data.get('code')
        discount = data.get('discount')
        max_uses = data.get('max_uses', 1)
        expires_at = data.get('expires_at')
        if create_promo(code, discount, max_uses, expires_at):
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error', 'error': 'Код уже существует'}), 400
    elif request.method == 'DELETE':
        if not _is_admin_request(request):
            return jsonify({'status': 'error', 'error': 'admin access required'}), 403
        data = request.json
        promo_id = data.get('id')
        cursor.execute("DELETE FROM promo_codes WHERE id = %s", (promo_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'status': 'success'})
    cursor.close()
    conn.close()

# Новый эндпоинт для обновления статуса заказа
@app.route('/api/order/<int:order_id>/status', methods=['POST'])
def update_order_status_endpoint(order_id):
    data = request.json or {}
    new_status = data.get('status')
    valid_statuses = ['pending', 'accepted', 'cooking', 'on_delivery', 'delivered', 'failed']

    if not new_status or new_status not in valid_statuses:
        return jsonify({'status': 'error', 'error': 'Invalid or missing status'}), 400

    # Проверка роли пользователя (простая проверка по Telegram ID)
    telegram_id = request.headers.get('X-Telegram-Id')  # Предполагаем, что ID передаётся в заголовке
    if not telegram_id:
        return jsonify({'status': 'error', 'error': 'Unauthorized'}), 401

    if str(telegram_id) != str(ADMIN_TELEGRAM_ID):
        role = get_user_role(int(telegram_id))
        if 'admin' not in role:
            return jsonify({'status': 'error', 'error': 'Only admins can update order status'}), 403

    if update_order_status(order_id, new_status):
        app.logger.info(f"Order {order_id} status updated to {new_status} by admin {telegram_id}")
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'error': 'Order not found'}), 404

# serve uploaded files
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Serve web app files (index.html, assets etc.)
@app.route('/web_app/<path:filename>')
def serve_webapp(filename):
    return send_from_directory('web_app', filename)

@app.route('/')
def index():
    return "API for Restaurant WebApp"

if __name__ == '__main__':
    # production: use gunicorn/uvicorn
    app.run(host='0.0.0.0', port=PORT, debug=DEBUG)