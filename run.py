"""Запуск Lead Scout: только веб-панель (Telegram-бот отключён)."""

from __future__ import annotations

import logging

import database as db
from config import LOG_FILE, PANEL_HOST, PANEL_PORT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE, encoding="utf-8")],
)


def main() -> None:
    db.init_db()
    from panel import app
    app.run(host=PANEL_HOST, port=PANEL_PORT, use_reloader=False)


if __name__ == "__main__":
    main()
