import os
from dotenv import load_dotenv

load_dotenv()


def _get_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Environment variable {name} is required for deployment.")
    return value


# ================== TELEGRAM ==================
BOT_TOKEN = _get_required("BOT_TOKEN")
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN", "")  # optional stub

# Only this Telegram ID получит доступ к админке и защищённым эндпоинтам
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", None)

# URL фронтенда (например, https://<railway-domain>/web_app/index.html)
WEB_APP_URL = os.getenv("WEB_APP_URL", "")

# ================== DATABASE (MySQL) ==================
# Railway даёт переменные MYSQLHOST / MYSQLUSER / MYSQLPASSWORD / MYSQLDATABASE
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST") or os.getenv("MYSQLHOST", "localhost"),
    "user": os.getenv("MYSQL_USER") or os.getenv("MYSQLUSER", "bot_user"),
    "password": os.getenv("MYSQL_PASSWORD") or os.getenv("MYSQLPASSWORD", "MyStrongPass123"),
    "database": os.getenv("MYSQL_DB") or os.getenv("MYSQLDATABASE", "restaurant_db"),
    "port": int(os.getenv("MYSQL_PORT") or os.getenv("MYSQLPORT", 3306)),
}

# ================== LOCALIZATION ==================
CURRENCY = os.getenv("CURRENCY", "BYN")
RESTAURANT_ADDRESS = os.getenv("RESTAURANT_ADDRESS", "ул. Советская, 1, Гомель, 246000")
YANDEX_MAPS_API_KEY = os.getenv("YANDEX_MAPS_API_KEY", "")

# ================== Runtime ==================
PORT = int(os.getenv("PORT", 5000))
DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"