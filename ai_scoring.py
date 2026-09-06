"""AI-оценка «боли автоматизации» организации + черновик персонального оффера.

Работает через любой OpenAI-совместимый API (Ollama, OpenRouter и т.д.).
Есть fallback на эвристику, если AI выключен или недоступен.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Tuple

from config import (
    AI_ENABLED, AI_BASE_URL, AI_API_KEY, AI_MODEL, AI_TIMEOUT,
    COMPANY_NAME, OUR_SERVICES, NICHES,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    f"Ты — аналитик агентства автоматизации «{COMPANY_NAME}». "
    f"Мы продаём: {OUR_SERVICES}.\n"
    "По данным об организации оцени, насколько ей нужна наша автоматизация.\n"
    "Сигналы высокой потребности: нет сайта, нет онлайн-записи, только телефон, "
    "много клиентов (много отзывов) при ручных процессах, ниша с записью/заказами.\n"
    "Сигналы низкой: уже есть сайт с онлайн-записью, сетевой бренд, ниша без "
    "потока клиентских обращений.\n"
    "Шкала: 1-3 — вряд ли купят; 4-6 — возможно; 7-8 — тёплый лид; "
    "9-10 — явная боль, звонить в первую очередь.\n"
    "Ответь СТРОГО в JSON без пояснений:\n"
    '{"score": <1-10>, "summary": "<2 предложения: почему такой балл>", '
    '"offer": "<3-4 предложения: черновик первого сообщения владельцу — '
    "вежливо, конкретно про его бизнес и его боль, без воды и без давления, "
    'с одним конкретным предложением>"}'
)


def _niche_title(niche_id: str) -> str:
    return next((n["title"] for n in NICHES if n["id"] == niche_id), niche_id)


def _niche_pain(niche_id: str) -> str:
    return next((n["pain"] for n in NICHES if n["id"] == niche_id), "")


def _build_prompt(lead: dict) -> str:
    return (
        f"Организация: {lead.get('name')}\n"
        f"Ниша: {_niche_title(lead.get('niche', ''))} "
        f"(типичные боли: {_niche_pain(lead.get('niche', ''))})\n"
        f"Адрес: {lead.get('address') or '—'}\n"
        f"Телефон: {lead.get('phone') or 'нет'}\n"
        f"Сайт: {lead.get('website') or 'НЕТ САЙТА'}\n"
        f"Соцсети: {lead.get('socials') or 'не найдены'}\n"
        f"Рейтинг 2ГИС: {lead.get('rating') or '—'}, "
        f"отзывов: {lead.get('reviews_count') or 0}"
    )


def heuristic_score(lead: dict) -> Tuple[int, str, str]:
    """Fallback-оценка без AI по простым правилам."""
    score = 5
    reasons = []
    if not lead.get("website"):
        score += 2
        reasons.append("нет сайта")
    if lead.get("socials") and not lead.get("website"):
        score += 1
        reasons.append("живут в соцсетях — привыкли к онлайну")
    reviews = lead.get("reviews_count") or 0
    if reviews > 50:
        score += 1
        reasons.append(f"поток клиентов ({reviews} отзывов)")
    if not lead.get("phone"):
        score -= 2
        reasons.append("нет телефона — сложно связаться")
    score = max(1, min(10, score))
    summary = "Эвристика: " + (", ".join(reasons) or "нет явных сигналов")
    offer = (
        f"Здравствуйте! Мы — {COMPANY_NAME}, автоматизируем "
        f"{_niche_title(lead.get('niche', '')).lower()} в Краснодаре: "
        f"{_niche_pain(lead.get('niche', ''))}. "
        "Могу за 10 минут показать, как это работает у похожих компаний — удобно созвониться?"
    )
    return score, summary, offer


async def score_lead(lead: dict) -> Tuple[int, str, str]:
    """Вернуть (score, summary, offer). При любой ошибке — эвристика."""
    if not AI_ENABLED:
        return heuristic_score(lead)
    import aiohttp  # ленивый импорт: эвристика работает и без aiohttp
    payload = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(lead)},
        ],
        "temperature": 0.4,
    }
    headers = {"Authorization": f"Bearer {AI_API_KEY}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{AI_BASE_URL}/chat/completions", json=payload,
                headers=headers, timeout=AI_TIMEOUT,
            ) as resp:
                data = await resp.json()
        text = data["choices"][0]["message"]["content"]
        match = re.search(r"\{.*\}", text, re.DOTALL)
        parsed = json.loads(match.group(0))
        score = max(1, min(10, int(parsed["score"])))
        return score, str(parsed.get("summary", "")), str(parsed.get("offer", ""))
    except Exception:
        logger.exception("AI-скоринг не удался, используем эвристику: %s", lead.get("name"))
        return heuristic_score(lead)
