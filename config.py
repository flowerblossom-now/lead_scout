"""Конфигурация Lead Scout — поиск малого бизнеса Краснодара для предложения автоматизации.

Секреты читаются из переменных окружения (файл .env).
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")

DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "leads.db")))

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
# Telegram ID менеджеров, которым бот шлёт лиды (через запятую)
MANAGER_CHAT_IDS = [
    int(x) for x in os.getenv("MANAGER_CHAT_IDS", "0").split(",") if x.strip().isdigit()
]

PANEL_HOST = os.getenv("PANEL_HOST", "0.0.0.0")
PANEL_PORT = int(os.getenv("PANEL_PORT", "5060"))
PANEL_SECRET_KEY = os.getenv("PANEL_SECRET_KEY", "change-me-in-production")
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "admin")

# --- Источник данных: 2ГИС Places API (https://docs.2gis.com/ru/api/search/places/overview)
DGIS_API_KEY = os.getenv("DGIS_API_KEY", "")
DGIS_BASE_URL = "https://catalog.api.2gis.com/3.0/items"
CITY_NAME = os.getenv("CITY_NAME", "Краснодар")
# region_id Краснодара в 2ГИС
DGIS_REGION_ID = os.getenv("DGIS_REGION_ID", "38")
SCAN_PAGE_SIZE = int(os.getenv("SCAN_PAGE_SIZE", "10"))
SCAN_MAX_PAGES = int(os.getenv("SCAN_MAX_PAGES", "3"))

# Ниши малого бизнеса, где автоматизация продаётся чаще всего.
# priority — базовый вес "боли" ниши (добавляется к AI-оценке сигналов).
NICHES = [
    {"id": "beauty", "query": "салон красоты", "title": "Салоны красоты", "emoji": "💇", "pain": "запись клиентов, напоминания, ведение базы"},
    {"id": "dental", "query": "стоматология", "title": "Стоматологии", "emoji": "🦷", "pain": "онлайн-запись, напоминания о приёме, повторные визиты"},
    {"id": "autoservice", "query": "автосервис", "title": "Автосервисы", "emoji": "🔧", "pain": "запись на ремонт, статусы заказа, учёт запчастей"},
    {"id": "fitness", "query": "фитнес клуб", "title": "Фитнес и студии", "emoji": "🏋️", "pain": "абонементы, расписание, продление, CRM"},
    {"id": "cafe", "query": "кофейня", "title": "Кафе и кофейни", "emoji": "☕", "pain": "доставка, программа лояльности, приём заказов"},
    {"id": "flowers", "query": "цветочный магазин", "title": "Цветочные", "emoji": "💐", "pain": "приём заказов в мессенджерах, доставка, витрина"},
    {"id": "cleaning", "query": "клининг", "title": "Клининг", "emoji": "🧹", "pain": "заявки, расчёт стоимости, график бригад"},
    {"id": "repair", "query": "ремонт квартир", "title": "Ремонт и стройка", "emoji": "🏗️", "pain": "лиды, сметы, статусы объектов для клиента"},
    {"id": "vet", "query": "ветеринарная клиника", "title": "Ветклиники", "emoji": "🐾", "pain": "запись, напоминания о прививках, карточки пациентов"},
    {"id": "tutor", "query": "языковая школа", "title": "Школы и курсы", "emoji": "📚", "pain": "расписание, оплата абонементов, уведомления родителям"},
]

# --- AI (любой OpenAI-совместимый API: Ollama, OpenRouter и т.д.)
AI_ENABLED = os.getenv("AI_ENABLED", "1") == "1"
AI_BASE_URL = os.getenv("AI_BASE_URL", "http://localhost:11434/v1")
AI_MODEL = os.getenv("AI_MODEL", "qwen3-vl:8b")
AI_API_KEY = os.getenv("AI_API_KEY", "ollama")
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "120"))

COMPANY_NAME = os.getenv("COMPANY_NAME", "Mindl")
# Кратко: что мы продаём. Используется в AI-промпте для генерации оффера.
OUR_SERVICES = os.getenv(
    "OUR_SERVICES",
    "Telegram-боты записи и приёма заказов, CRM-интеграции, сайты-визитки, "
    "автоматизация уведомлений и программы лояльности",
)

LOG_FILE = BASE_DIR / "scout.log"
