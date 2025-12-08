import os
from dotenv import load_dotenv

# Загружаем .env (если есть)
load_dotenv()

# ================== TELEGRAM ==================
BOT_TOKEN = os.getenv("BOT_TOKEN") or "8220961254:AAHBQiDPihdpVjYi9cJb_PW-o30KNTvhIH0"

if not BOT_TOKEN or ":" not in BOT_TOKEN:
    raise ValueError("❌ Ошибка: BOT_TOKEN не найден или неверный. Проверь .env или config.py")

WEB_APP_URL = "https://pliable-unpunctuating-stacey.ngrok-free.dev"
# ================== DATABASE (MySQL) ==================
MYSQL_CONFIG = {
    'host': os.getenv("MYSQL_HOST", "localhost"),
    'user': os.getenv("MYSQL_USER", "bot_user"),
    'password': os.getenv("MYSQL_PASSWORD", "MyStrongPass123"),
    'database': os.getenv("MYSQL_DB", "restaurant_db"),
}

# ================== Crypto BOT ===================
# config.py
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN", "465695:AAmnhDHAI79JLCEYAUcjQBYwio8wJjW0DA0")

# ================== LOCALIZATION ==================
CURRENCY = os.getenv("CURRENCY", "BYN")
RESTAURANT_ADDRESS = os.getenv("RESTAURANT_ADDRESS", "ул. Советская, 1, Гомель, 246000")
YANDEX_MAPS_API_KEY = os.getenv("YANDEX_MAPS_API_KEY", "09b5ff38-21a8-4d1d-a0a2-a08e12528dcc")  # Твой ключ