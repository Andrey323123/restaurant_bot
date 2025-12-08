import mysql.connector
from mysql.connector import Error
from config import MYSQL_CONFIG
import json
from datetime import datetime
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_connection():
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        if conn.is_connected():
            return conn
    except Error as e:
        logger.error(f"Ошибка подключения: {e}")
        return None

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    # users: telegram_id, username, role (user/admin/courier/delivery)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        telegram_id BIGINT PRIMARY KEY,
        username VARCHAR(255) UNIQUE,
        role VARCHAR(20) DEFAULT 'user'
    )
    ''')

    # dishes: supports image_url, category and sizes (JSON)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS dishes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(200),
        price DECIMAL(10,2),
        description TEXT,
        image_url TEXT,
        category VARCHAR(100),
        sizes JSON NULL
    )
    ''')

    # orders (обновлено поле status и добавлено courier_id, order_type, pickup_notified)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT NOT NULL,
        dishes JSON NOT NULL,
        address TEXT NOT NULL,
        total DECIMAL(10,2) DEFAULT 0,
        status VARCHAR(30) DEFAULT 'pending',
        courier_id BIGINT DEFAULT NULL,
        order_type VARCHAR(20) DEFAULT 'delivery',  -- Новый параметр для типа заказа
        payment_provider VARCHAR(100),
        payment_id VARCHAR(255),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        notified DATETIME NULL,
        pickup_notified DATETIME NULL  -- Новый параметр для уведомлений о готовности самовывоза
    )
    ''')

    # promotions
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS promotions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        text VARCHAR(255),
        image_url TEXT
    )
    ''')

    # promo_codes
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS promo_codes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        code VARCHAR(50) UNIQUE NOT NULL,
        discount DECIMAL(5,2) NOT NULL,  -- процент скидки (например, 20.00)
        max_uses INT DEFAULT 1,          -- максимум использований
        uses INT DEFAULT 0,              -- текущее количество использований
        expires_at DATE,                 -- дата истечения (YYYY-MM-DD)
        is_active BOOLEAN DEFAULT TRUE,  -- активен ли
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    cursor.close()
    conn.close()

# user helpers
def add_user(telegram_id, role='user', username=None):
    conn = get_connection()
    cursor = conn.cursor()
    # Если telegram_id отсутствует, используем 0 как временный идентификатор
    telegram_id = telegram_id if telegram_id is not None else 0
    try:
        cursor.execute("INSERT IGNORE INTO users (telegram_id, username, role) VALUES (%s, %s, %s)",
                       (telegram_id, username, role))
        conn.commit()
        return True
    except Error as e:
        logger.error(f"Ошибка добавления пользователя: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def set_user_role_by_username(username, role):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET role = %s WHERE username = %s", (role, username))
        conn.commit()
        return cursor.rowcount > 0
    except Error as e:
        logger.error(f"Ошибка установки роли: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def set_user_username(telegram_id, username):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET username = %s WHERE telegram_id = %s", (username, telegram_id))
        conn.commit()
        return cursor.rowcount > 0
    except Error as e:
        logger.error(f"Ошибка обновления username: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_user_role(telegram_id=None, username=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if telegram_id:
            cursor.execute("SELECT role FROM users WHERE telegram_id = %s", (telegram_id,))
        elif username:
            cursor.execute("SELECT role FROM users WHERE username = %s", (username,))
        else:
            cursor.close()
            conn.close()
            return 'user'
        r = cursor.fetchone()
        return r[0] if r else 'user'
    except Error as e:
        logger.error(f"Ошибка получения роли: {e}")
        return 'user'
    finally:
        cursor.close()
        conn.close()

def get_user_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT telegram_id, role FROM users WHERE username = %s", (username,))
        r = cursor.fetchone()
        return {'telegram_id': r[0], 'role': r[1]} if r else None
    except Error as e:
        logger.error(f"Ошибка поиска пользователя: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def get_admin_username():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT username FROM users WHERE role = 'admin' LIMIT 1")
        r = cursor.fetchone()
        return r[0] if r else None
    except Error as e:
        logger.error(f"Ошибка получения админа: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

# dishes
def add_dish(name, price, description=None, image_url=None, category='other', sizes=None):
    conn = get_connection()
    cursor = conn.cursor()
    sizes_json = json.dumps(sizes) if sizes else None
    try:
        cursor.execute("INSERT INTO dishes (name, price, description, image_url, category, sizes) VALUES (%s, %s, %s, %s, %s, %s)",
                       (name, price, description, image_url, category, sizes_json))
        conn.commit()
        return True
    except Error as e:
        logger.error(f"Ошибка добавления блюда: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def remove_dish(dish_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM dishes WHERE id = %s", (dish_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Error as e:
        logger.error(f"Ошибка удаления блюда: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_dishes(category=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if category:
            cursor.execute("SELECT id, name, price, description, image_url, category, sizes FROM dishes WHERE category = %s", (category,))
        else:
            cursor.execute("SELECT id, name, price, description, image_url, category, sizes FROM dishes")
        rows = cursor.fetchall()
        dishes = []
        for r in rows:
            sizes = None
            try:
                sizes = json.loads(r[6]) if r[6] else None
            except:
                sizes = None
            dishes.append({
                "id": r[0],
                "name": r[1],
                "price": float(r[2]),
                "description": r[3],
                "image_url": r[4],
                "category": r[5],
                "sizes": sizes
            })
        return dishes
    except Error as e:
        logger.error(f"Ошибка получения блюд: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

# orders
def add_order(user_id, dishes_json, address, total, order_type='delivery', payment_provider=None, payment_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Проверяем total, если он передан как 0 или None, рассчитываем из dishes_json
        if total <= 0:
            dishes = json.loads(dishes_json)
            total = sum(float(d.get('price', 0)) * (d.get('qty', 1) or 1) for d in dishes)
        cursor.execute("""
            INSERT INTO orders (user_id, dishes, address, total, status, order_type, payment_provider, payment_id)
            VALUES (%s, %s, %s, %s, 'pending', %s, %s, %s)
        """, (user_id, dishes_json, address, total, order_type, payment_provider, payment_id))
        conn.commit()
        cursor.execute("SELECT LAST_INSERT_ID()")
        order_id = cursor.fetchone()[0]
        logger.info(f"Added order {order_id} for user {user_id} with type {order_type}")
        return order_id  # Возвращаем order_id
    except Error as e:
        logger.error(f"Ошибка добавления заказа: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def get_new_orders():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, user_id, dishes, address, total, status, order_type FROM orders WHERE status = 'pending'")
        rows = cursor.fetchall()
        return [(r[0], r[1], r[2], r[3], r[4], r[5], r[6]) for r in rows]  # Добавили order_type
    except Error as e:
        logger.error(f"Ошибка получения новых заказов: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def update_order_status(order_id, status, courier_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if courier_id:
            cursor.execute("UPDATE orders SET status = %s, courier_id = %s WHERE id = %s", (status, courier_id, order_id))
        else:
            cursor.execute("UPDATE orders SET status = %s WHERE id = %s", (status, order_id))
        conn.commit()
        return cursor.rowcount > 0
    except Error as e:
        logger.error(f"Ошибка обновления статуса заказа: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_user_id_by_order_id(order_id):
    """Получает user_id по order_id."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id FROM orders WHERE id = %s", (order_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    except Error as e:
        logger.error(f"Ошибка получения user_id для заказа {order_id}: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

# promo_codes
def create_promo(code, discount, max_uses=1, expires_at=None):
    conn = get_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO promo_codes (code, discount, max_uses, expires_at)
            VALUES (%s, %s, %s, %s)
        """, (code.upper(), discount, max_uses, expires_at))
        conn.commit()
        return True
    except Error as e:
        logger.error(f"Ошибка создания промокода: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def validate_promo(code):
    conn = get_connection()
    if not conn:
        logger.error("No database connection")
        return {'valid': False}
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT discount, uses, max_uses, expires_at, is_active
            FROM promo_codes
            WHERE code = %s AND is_active = TRUE
        """, (code.upper(),))
        row = cursor.fetchone()
        if row:
            discount, uses, max_uses, expires_at, is_active = row
            current_date = datetime.now().date()
            valid = (uses < max_uses and (expires_at is None or current_date <= expires_at))
            logger.info(f"Validating promo {code}: uses={uses}, max_uses={max_uses}, expires_at={expires_at}, valid={valid}")
            return {'discount': float(discount), 'valid': valid}
        logger.info(f"Promo code {code} not found or inactive")
        return {'valid': False}
    except Error as e:
        logger.error(f"Ошибка валидации промокода: {e}")
        return {'valid': False}
    finally:
        cursor.close()
        conn.close()

def use_promo(code):
    conn = get_connection()
    if not conn:
        logger.error("No database connection")
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE promo_codes SET uses = uses + 1
            WHERE code = %s AND is_active = TRUE
        """, (code.upper(),))
        conn.commit()
        success = cursor.rowcount > 0
        if success:
            logger.info(f"Promo code {code} used successfully")
        else:
            logger.warning(f"Failed to use promo code {code}")
        return success
    except Error as e:
        logger.error(f"Ошибка использования промокода: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_all_promocodes():
    conn = get_connection()
    if not conn:
        logger.error("No database connection")
        return []
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT code, discount, max_uses, uses, expires_at, is_active FROM promo_codes ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [{'code': r[0], 'discount': float(r[1]), 'max_uses': r[2], 'uses': r[3], 'expires_at': r[4], 'is_active': bool(r[5])} for r in rows]
    except Error as e:
        logger.error(f"Ошибка получения промокодов: {e}")
        return []
    finally:
        cursor.close()
        conn.close()