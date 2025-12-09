# Railway deployment notes

1) **Environment variables**
   - `BOT_TOKEN` – Telegram bot token.
   - `ADMIN_TELEGRAM_ID` – числовой Telegram ID администратора (только он увидит админку и сможет вызывать защищённые API).
   - `ADMIN_USERNAME` – опционально, username админа для уведомлений.
   - `WEB_APP_URL` – публичная ссылка на веб-приложение (например, `https://<railway-domain>/web_app/index.html`).
   - `MYSQLHOST`, `MYSQLUSER`, `MYSQLPASSWORD`, `MYSQLDATABASE`, `MYSQLPORT` – выдаются Railway при добавлении MySQL.
   - Дополнительно при необходимости: `RESTAURANT_ADDRESS`, `CURRENCY`, `YANDEX_MAPS_API_KEY`.

2) **Services**
   - Web service: start command `gunicorn api:app --bind 0.0.0.0:$PORT` (также указано в `Procfile` и `railway.toml`).
   - Бот (`bot.py`) можно поднять отдельным worker-сервисом со стартовой командой `python bot.py` (требует те же env).

3) **Static**
   - Фронт (`web_app`) обслуживается Flask'ом по пути `/web_app`. Страница админки запрашивает `X-Telegram-Id` и сверяет с `ADMIN_TELEGRAM_ID`.

