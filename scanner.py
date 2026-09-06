"""Сканер организаций Краснодара через официальный 2ГИС Places API.

Собирает по нишам из config.NICHES: название, адрес, телефон, сайт, соцсети,
рейтинг и число отзывов — это сигналы для AI-оценки потребности в автоматизации.

Ключ API: https://dev.2gis.ru (бесплатный тариф достаточен для старта).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, AsyncIterator

if TYPE_CHECKING:
    import aiohttp

from config import (
    DGIS_API_KEY, DGIS_BASE_URL, DGIS_REGION_ID, CITY_NAME,
    SCAN_PAGE_SIZE, SCAN_MAX_PAGES, NICHES,
)

logger = logging.getLogger(__name__)

FIELDS = ",".join([
    "items.point", "items.address", "items.contact_groups",
    "items.reviews", "items.org", "items.rubrics", "items.schedule",
])


def _extract_contacts(item: dict) -> dict:
    phone = website = None
    socials: list[str] = []
    for group in item.get("contact_groups", []) or []:
        for c in group.get("contacts", []) or []:
            ctype, value = c.get("type"), c.get("value") or c.get("url")
            if ctype == "phone" and not phone:
                phone = value
            elif ctype == "website" and not website:
                website = value
            elif ctype in ("vkontakte", "telegram", "whatsapp", "instagram", "odnoklassniki"):
                socials.append(f"{ctype}: {value}")
    return {"phone": phone, "website": website, "socials": "; ".join(socials) or None}


def _parse_item(item: dict, niche_id: str) -> dict:
    contacts = _extract_contacts(item)
    reviews = item.get("reviews", {}) or {}
    return {
        "dgis_id": str(item.get("id")),
        "name": item.get("name", "?"),
        "niche": niche_id,
        "address": item.get("address_name") or (item.get("address", {}) or {}).get("name"),
        "phone": contacts["phone"],
        "website": contacts["website"],
        "socials": contacts["socials"],
        "rating": reviews.get("general_rating"),
        "reviews_count": reviews.get("general_review_count"),
        "raw_json": json.dumps(item, ensure_ascii=False),
    }


async def scan_niche(session: "aiohttp.ClientSession", niche: dict) -> AsyncIterator[dict]:
    """Постранично выгрузить организации одной ниши."""
    for page in range(1, SCAN_MAX_PAGES + 1):
        params = {
            "q": f"{niche['query']} {CITY_NAME}",
            "region_id": DGIS_REGION_ID,
            "page": page,
            "page_size": SCAN_PAGE_SIZE,
            "fields": FIELDS,
            "key": DGIS_API_KEY,
        }
        try:
            async with session.get(DGIS_BASE_URL, params=params, timeout=30) as resp:
                data = await resp.json()
        except Exception:
            logger.exception("2ГИС: ошибка запроса, ниша=%s стр=%s", niche["id"], page)
            return
        items = (data.get("result") or {}).get("items") or []
        if not items:
            return
        for item in items:
            yield _parse_item(item, niche["id"])


async def scan_all(niche_ids: list[str] | None = None) -> list[dict]:
    """Просканировать все (или выбранные) ниши. Возвращает список лидов."""
    import aiohttp  # ленивый импорт
    if not DGIS_API_KEY:
        raise RuntimeError("Не задан DGIS_API_KEY в .env — получи ключ на dev.2gis.ru")
    selected = [n for n in NICHES if not niche_ids or n["id"] in niche_ids]
    results: list[dict] = []
    async with aiohttp.ClientSession() as session:
        for niche in selected:
            logger.info("Сканирую нишу: %s", niche["title"])
            async for lead in scan_niche(session, niche):
                results.append(lead)
    logger.info("Собрано организаций: %d", len(results))
    return results
