import asyncio
import json
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from database import init_db, add_user, get_user_role, add_order, get_connection, get_admin_username, add_dish, set_user_username, set_user_role_by_username, create_promo, get_new_orders, get_user_id_by_order_id, update_order_status
from config import BOT_TOKEN, WEB_APP_URL

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# Статусы заказа
ORDER_STATUSES = ['pending', 'accepted', 'cooking', 'on_delivery', 'delivered', 'failed']

# /start
@dp.message(Command('start'))
async def start(message: types.Message):
    username = message.from_user.username or ''
    add_user(message.from_user.id, 'user', username)
    set_user_username(message.from_user.id, username)
    role = get_user_role(message.from_user.id)
    logger.info(f"User {message.from_user.id} logged in with role: {role}")
    if "user" in role:
        keyboard = ReplyKeyboardMarkup(
            resize_keyboard=True,
            keyboard=[[KeyboardButton(text="Открыть меню", web_app=WebAppInfo(url=WEB_APP_URL))]]
        )
        await message.answer("Добро пожаловать! Откройте меню:", reply_markup=keyboard)
    if "courier" in role:
        await message.answer("Привет, курьер! Используй /courier_orders, /accept_order [id], /start_cooking [id], /start_delivery [id], /complete_order [id]")
    if "admin" in role:
        await message.answer("Привет, админ! Открой /admin в браузере для управления.")

# /init_admin — назначение первого админа
@dp.message(Command('init_admin'))
async def init_admin(message: types.Message):
    existing = get_admin_username()
    if existing:
        await message.answer("Админ уже назначен.")
        return
    username = message.from_user.username
    if not username:
        await message.answer("Нужен username в профиле Telegram.")
        return
    add_user(message.from_user.id, 'admin', username)
    set_user_role_by_username(username, 'admin')
    await message.answer("Вы назначены админом.")

# /createpromo — создание промокода для админов
@dp.message(Command('createpromo'))
async def create_promo_cmd(message: types.Message):
    role = get_user_role(message.from_user.id)
    if "admin" not in role:
        await message.answer("Только для админов.")
        return
    args = message.text.split()[1:]  # code discount max_uses expires_at
    if len(args) < 2:
        await message.answer("Формат: /createpromo <code> <discount%> [max_uses] [expires_at]")
        return
    code, discount = args[0], args[1]
    max_uses = int(args[2]) if len(args) > 2 else 1
    expires_at = args[3] if len(args) > 3 else None
    if create_promo(code, float(discount), max_uses, expires_at):
        await message.answer(f"Промокод {code} создан!")
    else:
        await message.answer("Ошибка: код уже существует.")

# /add_courier_role — добавление роли курьера для админа
@dp.message(Command('add_courier_role'))
async def add_courier_role(message: types.Message):
    role = get_user_role(message.from_user.id)
    if "admin" not in role:
        await message.answer("Только для админов.")
        return
    args = message.text.split()[1:]  # telegram_id
    if len(args) != 1:
        await message.answer("Формат: /add_courier_role <telegram_id>")
        return
    telegram_id = int(args[0])
    current_role = get_user_role(telegram_id)
    if not current_role:
        await message.answer("Пользователь не найден.")
        return
    if "courier" not in current_role:
        new_role = json.dumps(list(set(json.loads(current_role) + ["courier"])))
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET role = %s WHERE telegram_id = %s", (new_role, telegram_id))
            conn.commit()
            await message.answer(f"Роль 'courier' добавлена для пользователя {telegram_id}.")
        except Exception as e:
            logger.error(f"Ошибка обновления роли: {e}")
            await message.answer("Ошибка при обновлении роли.")
        finally:
            cursor.close()
            conn.close()
    else:
        await message.answer(f"У пользователя {telegram_id} уже есть роль 'courier'.")

# /help — помощь для курьеров
@dp.message(Command('help'))
async def help_command(message: types.Message):
    role = get_user_role(message.from_user.id)
    if "courier" not in role:
        await message.answer("Эта команда доступна только курьерам.")
        return

    help_text = (
        "📋 Список команд для курьеров:\n\n"
        "/courier_orders — Показать список новых заказов с их статусами, адресами и суммами.\n"
        "/accept_order [id] — Принять заказ с указанным ID. Статус изменится на 'accepted'.\n"
        "/start_cooking [id] — Указать, что заказ с ID начал готовиться. Статус изменится на 'cooking'.\n"
        "/start_delivery [id] — Начать доставку заказа с ID. Статус изменится на 'on_delivery' (только для доставки).\n"
        "/complete_order [id] — Завершить заказ с ID. Статус изменится на 'delivered'.\n\n"
        "Пример: /accept_order 123\n"
        "Используйте ID из списка заказов для управления."
    )
    await message.answer(help_text)

# Обработка сообщений
@dp.message()
async def handle_message(message: types.Message):
    role = get_user_role(message.from_user.id)
    logger.info(f"Received message from {message.from_user.id} with role {role}: {message.text}")

    # Заказы из WebApp
    if message.web_app_data:
        try:
            data = json.loads(message.web_app_data.data)
            dishes = data.get('dishes', [])
            address = data.get('address', '')
            total = data.get('total', 0.0)
            order_type = data.get('orderType', 'delivery')  # Получаем тип заказа
            order_id = add_order(message.from_user.id, json.dumps(dishes), address, total, order_type)
            if order_id:
                await message.answer(f"Заказ #{order_id} получен! Ожидайте подтверждения.")
                # Извлекаем названия блюд с количеством
                decoded_dishes = json.loads(json.dumps(dishes, ensure_ascii=False))
                dish_names = [f"{dish['name']} x{dish['qty']}" for dish in decoded_dishes]
                dishes_str = ", ".join(dish_names)
                # Уведомление админу
                admin_username = get_admin_username()
                if admin_username:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT telegram_id FROM users WHERE username = %s", (admin_username,))
                    admin_id = cursor.fetchone()
                    cursor.close()
                    conn.close()
                    if admin_id:
                        await bot.send_message(admin_id[0], f"Новый заказ #{order_id}\nТип: {order_type}\nПользователь: {message.from_user.id}\nАдрес: {address}\nБлюда: {dishes_str}\nСумма: {total} BYN\nСтатус: pending")
                # Уведомление курьерам
                conn = get_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT telegram_id FROM users WHERE JSON_CONTAINS(role, '\"courier\"')")
                    couriers = cursor.fetchall()
                    cursor.close()
                    conn.close()
                    for courier in couriers:
                        try:
                            await bot.send_message(courier[0], f"Новый заказ #{order_id}! Используй /courier_orders\nТип: {order_type}\nСтатус: pending")
                        except Exception as e:
                            logger.error(f"Ошибка отправки курьеру {courier[0]}: {e}")
            else:
                await message.answer("Ошибка создания заказа.")
            return
        except Exception as e:
            logger.error(f"Ошибка обработки WebApp данных: {e}")
            await message.answer(f"Ошибка обработки данных: {e}")
            return

    # Заказы курьерам
    if "courier" in role:
        if message.text == '/courier_orders':
            orders = get_new_orders()
            logger.info(f"Orders retrieved for courier: {orders}")
            if not orders:
                await message.answer("Нет новых заказов.")
                return
            for order in orders:
                order_id, user_id, dishes, address, total, status, order_type = order  # Добавили order_type
                decoded_dishes = json.loads(dishes) if dishes else []
                dish_names = [f"{dish['name']} x{dish['qty']}" for dish in decoded_dishes]
                dishes_str = ", ".join(dish_names)
                await message.answer(f"Заказ #{order_id}\nОт: {user_id}\nТип: {order_type}\nАдрес: {address}\nБлюда: {dishes_str}\nСумма: {total} BYN\nСтатус: {status}")
            return

        elif message.text.startswith('/accept_order'):
            try:
                order_id = int(message.text.split()[1])
                if update_order_status(order_id, 'accepted', message.from_user.id):
                    user_id = get_user_id_by_order_id(order_id)
                    if user_id:
                        await bot.send_message(user_id, f"✅ Ваш заказ #{order_id} принят курьером!")
                    await message.answer(f"Заказ #{order_id} принят.\nСтатус обновлён: accepted")
                    # Уведомление курьерам и админу
                    conn = get_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT telegram_id FROM users WHERE JSON_CONTAINS(role, '\"courier\"')")
                        couriers = cursor.fetchall()
                        cursor.close()
                        conn.close()
                        for courier in couriers:
                            await bot.send_message(courier[0], f"Заказ #{order_id} принят.\nСтатус: accepted")
                        # Уведомление админу
                        admin_username = get_admin_username()
                        if admin_username:
                            cursor = conn.cursor()
                            cursor.execute("SELECT telegram_id FROM users WHERE username = %s", (admin_username,))
                            admin_id = cursor.fetchone()
                            cursor.close()
                            if admin_id:
                                await bot.send_message(admin_id[0], f"Заказ #{order_id} принят.\nСтатус: accepted")
                else:
                    await message.answer(f"Заказ #{order_id} не найден или уже обработан.")
            except (IndexError, ValueError):
                await message.answer("Формат: /accept_order [id]")

        elif message.text.startswith('/start_cooking'):
            try:
                order_id = int(message.text.split()[1])
                if update_order_status(order_id, 'cooking', message.from_user.id):
                    user_id = get_user_id_by_order_id(order_id)
                    if user_id:
                        await bot.send_message(user_id, f"🍳 Ваш заказ #{order_id} готовится!")
                    await message.answer(f"Заказ #{order_id} переведён в статус: cooking")
                    # Уведомление курьерам и админу
                    conn = get_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT telegram_id FROM users WHERE JSON_CONTAINS(role, '\"courier\"')")
                        couriers = cursor.fetchall()
                        cursor.close()
                        conn.close()
                        for courier in couriers:
                            await bot.send_message(courier[0], f"Заказ #{order_id} готовится.\nСтатус: cooking")
                        # Уведомление админу
                        admin_username = get_admin_username()
                        if admin_username:
                            cursor = conn.cursor()
                            cursor.execute("SELECT telegram_id FROM users WHERE username = %s", (admin_username,))
                            admin_id = cursor.fetchone()
                            cursor.close()
                            if admin_id:
                                await bot.send_message(admin_id[0], f"Заказ #{order_id} готовится.\nСтатус: cooking")
                else:
                    await message.answer(f"Заказ #{order_id} не найден или уже обработан.")
            except (IndexError, ValueError):
                await message.answer("Формат: /start_cooking [id]")

        elif message.text.startswith('/start_delivery'):
            try:
                order_id = int(message.text.split()[1])
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT order_type FROM orders WHERE id = %s", (order_id,))
                order_type = cursor.fetchone()
                cursor.close()
                conn.close()
                if order_type and order_type[0] == 'delivery' and update_order_status(order_id, 'on_delivery', message.from_user.id):
                    user_id = get_user_id_by_order_id(order_id)
                    if user_id:
                        await bot.send_message(user_id, f"🚚 Ваш заказ #{order_id} в доставке!")
                    await message.answer(f"Заказ #{order_id} переведён в статус: on_delivery")
                    # Уведомление курьерам и админу
                    conn = get_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT telegram_id FROM users WHERE JSON_CONTAINS(role, '\"courier\"')")
                        couriers = cursor.fetchall()
                        cursor.close()
                        conn.close()
                        for courier in couriers:
                            await bot.send_message(courier[0], f"Заказ #{order_id} в доставке.\nСтатус: on_delivery")
                        # Уведомление админу
                        admin_username = get_admin_username()
                        if admin_username:
                            cursor = conn.cursor()
                            cursor.execute("SELECT telegram_id FROM users WHERE username = %s", (admin_username,))
                            admin_id = cursor.fetchone()
                            cursor.close()
                            if admin_id:
                                await bot.send_message(admin_id[0], f"Заказ #{order_id} в доставке.\nСтатус: on_delivery")
                else:
                    await message.answer(f"Заказ #{order_id} не является доставкой или уже обработан.")
            except (IndexError, ValueError):
                await message.answer("Формат: /start_delivery [id]")

        elif message.text.startswith('/complete_order'):
            try:
                order_id = int(message.text.split()[1])
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT order_type FROM orders WHERE id = %s", (order_id,))
                order_type = cursor.fetchone()
                cursor.close()
                conn.close()
                if order_type and update_order_status(order_id, 'delivered', message.from_user.id):
                    user_id = get_user_id_by_order_id(order_id)
                    if user_id:
                        await bot.send_message(user_id, f"🎉 Ваш заказ #{order_id} {order_type[0] == 'delivery' and 'доставлен' or 'готов к самовывозу'}! Спасибо!")
                    await message.answer(f"Заказ #{order_id} отмечен как {order_type[0] == 'delivery' and 'доставлен' or 'готов к самовывозу'}.\nСтатус: delivered")
                    # Уведомление курьерам и админу
                    conn = get_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT telegram_id FROM users WHERE JSON_CONTAINS(role, '\"courier\"')")
                        couriers = cursor.fetchall()
                        cursor.close()
                        conn.close()
                        for courier in couriers:
                            await bot.send_message(courier[0], f"Заказ #{order_id} {order_type[0] == 'delivery' and 'доставлен' or 'готов к самовывозу'}.\nСтатус: delivered")
                        # Уведомление админу
                        admin_username = get_admin_username()
                        if admin_username:
                            cursor = conn.cursor()
                            cursor.execute("SELECT telegram_id FROM users WHERE username = %s", (admin_username,))
                            admin_id = cursor.fetchone()
                            cursor.close()
                            if admin_id:
                                await bot.send_message(admin_id[0], f"Заказ #{order_id} {order_type[0] == 'delivery' and 'доставлен' or 'готов к самовывозу'}.\nСтатус: delivered")
                else:
                    await message.answer(f"Заказ #{order_id} не найден или уже обработан.")
            except (IndexError, ValueError):
                await message.answer("Формат: /complete_order [id]")

    # Fallback
    await message.answer("Команда не распознана. Для курьера: /courier_orders, /accept_order [id], /start_cooking [id], /start_delivery [id], /complete_order [id], /help", parse_mode=None)

# Фоновое задание для проверки статуса заказов с уникальными уведомлениями
async def check_orders_periodically():
    while True:
        conn = get_connection()
        if conn:
            cursor = conn.cursor()
            try:
                # Проверяем заказы со всеми статусами с учётом флага notified
                cursor.execute("""
                    SELECT id, user_id, status, order_type 
                    FROM orders 
                    WHERE status IN ('accepted', 'cooking', 'on_delivery', 'delivered') 
                    AND (notified IS NULL OR notified < NOW() - INTERVAL 1 DAY)
                """)
                orders = cursor.fetchall()
                for order_id, user_id, status, order_type in orders:
                    if status == 'accepted':
                        await bot.send_message(user_id, f"✅ Ваш заказ #{order_id} принят курьером!")
                    elif status == 'cooking':
                        await bot.send_message(user_id, f"🍳 Ваш заказ #{order_id} готовится!")
                    elif status == 'on_delivery' and order_type == 'delivery':
                        await bot.send_message(user_id, f"🚚 Ваш заказ #{order_id} в доставке!")
                    elif status == 'delivered':
                        await bot.send_message(user_id, f"🎉 Ваш заказ #{order_id} {order_type == 'delivery' and 'доставлен' or 'готов к самовывозу'}! Спасибо!")
                    # Обновляем флаг notified
                    cursor.execute("UPDATE orders SET notified = NOW() WHERE id = %s", (order_id,))
                conn.commit()
            except Exception as e:
                logger.error(f"Ошибка проверки заказов: {e}")
            finally:
                cursor.close()
                conn.close()
        await asyncio.sleep(60)  # Проверка каждую минуту

# Обработка готовности заказов на самовывоз
async def check_pickup_readiness():
    while True:
        conn = get_connection()
        if conn:
            cursor = conn.cursor()
            try:
                # Проверяем заказы со статусом 'cooking' и типом 'restaurant'
                cursor.execute("""
                    SELECT id, user_id 
                    FROM orders 
                    WHERE status = 'cooking' 
                    AND order_type = 'restaurant' 
                    AND (pickup_notified IS NULL OR pickup_notified < NOW() - INTERVAL 1 HOUR)
                """)
                orders = cursor.fetchall()
                for order_id, user_id in orders:
                    # Симулируем задержку в 30 минут (в реальности можно использовать timestamp)
                    await asyncio.sleep(1800)  # 30 минут = 1800 секунд
                    if update_order_status(order_id, 'delivered', None):  # Автоматически завершаем как готовый к самовывозу
                        await bot.send_message(user_id, f"🍽 Ваш заказ #{order_id} готов к самовывозу! Среднее время ожидания истекло (~30 минут). Приезжайте в ресторан.")
                        cursor.execute("UPDATE orders SET pickup_notified = NOW() WHERE id = %s", (order_id,))
                        conn.commit()
            except Exception as e:
                logger.error(f"Ошибка проверки готовности самовывоза: {e}")
            finally:
                cursor.close()
                conn.close()
        await asyncio.sleep(60)  # Проверка каждую минуту

# Основная функция запуска
async def main():
    init_db()
    print("Бот запущен")
    asyncio.create_task(check_orders_periodically())
    asyncio.create_task(check_pickup_readiness())  # Добавляем задачу для проверки самовывоза
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        print("Бот остановлен")

if __name__ == '__main__':
    asyncio.run(main())