"""Telegram-бот Lead Scout для менеджера.

Команды:
  /scan            — просканировать все ниши
  /scan beauty     — просканировать одну нишу
  /top             — топ-5 необработанных лидов
  /niches          — список ниш
Кнопки на карточке лида: смена статуса, показать оффер.

Бот работает только для MANAGER_CHAT_IDS — это внутренний инструмент,
он НЕ рассылает сообщения бизнесам (холодный контакт делает человек).
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)

import database as db
from ai_scoring import score_lead
from config import BOT_TOKEN, MANAGER_CHAT_IDS, NICHES, CITY_NAME
from scanner import scan_all

logger = logging.getLogger(__name__)

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


def _is_manager(msg: Message | CallbackQuery) -> bool:
    uid = msg.from_user.id if msg.from_user else 0
    return not MANAGER_CHAT_IDS or uid in MANAGER_CHAT_IDS


def _lead_card(lead) -> str:
    niche = next((n for n in NICHES if n["id"] == lead["niche"]), {})
    return (
        f"{niche.get('emoji', '🏢')} <b>{lead['name']}</b>\n"
        f"Ниша: {niche.get('title', lead['niche'])}\n"
        f"📍 {lead['address'] or '—'}\n"
        f"📞 {lead['phone'] or '—'}\n"
        f"🌐 {lead['website'] or 'нет сайта'}\n"
        f"⭐ {lead['rating'] or '—'} ({lead['reviews_count'] or 0} отзывов)\n"
        f"🎯 <b>AI-балл: {lead['ai_score'] or '?'}/10</b>\n"
        f"<i>{lead['ai_summary'] or ''}</i>\n"
        f"Статус: {lead['status']}"
    )


def _lead_kb(lead_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Оффер", callback_data=f"offer:{lead_id}"),
            InlineKeyboardButton(text="▶️ В работу", callback_data=f"st:{lead_id}:в работе"),
        ],
        [
            InlineKeyboardButton(text="📨 КП отправлено", callback_data=f"st:{lead_id}:отправлено КП"),
            InlineKeyboardButton(text="🤝 Клиент", callback_data=f"st:{lead_id}:клиент"),
        ],
        [
            InlineKeyboardButton(text="❌ Отказ", callback_data=f"st:{lead_id}:отказ"),
            InlineKeyboardButton(text="🗑 Не подходит", callback_data=f"st:{lead_id}:не подходит"),
        ],
    ])


@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    if not _is_manager(message):
        return
    await message.answer(
        f"🔎 <b>Lead Scout — {CITY_NAME}</b>\n\n"
        "Ищу малый бизнес, которому нужна автоматизация.\n\n"
        "/scan — сканировать все ниши\n"
        "/scan beauty — одну нишу\n"
        "/niches — список ниш\n"
        "/top — лучшие необработанные лиды",
        parse_mode="HTML",
    )


@dp.message(Command("niches"))
async def cmd_niches(message: Message) -> None:
    if not _is_manager(message):
        return
    lines = [f"{n['emoji']} <code>{n['id']}</code> — {n['title']}" for n in NICHES]
    await message.answer("\n".join(lines), parse_mode="HTML")


@dp.message(Command("scan"))
async def cmd_scan(message: Message, command: CommandObject) -> None:
    if not _is_manager(message):
        return
    niche_ids = command.args.split() if command.args else None
    await message.answer("⏳ Сканирую 2ГИС, это займёт минуту-две…")
    try:
        leads = await scan_all(niche_ids)
    except RuntimeError as exc:
        await message.answer(f"⚠️ {exc}")
        return
    new_count = 0
    scored = []
    for data in leads:
        lead_id, is_new = db.upsert_lead(data)
        if is_new:
            new_count += 1
            score, summary, offer = await score_lead(data)
            db.save_ai_result(lead_id, score, summary, offer)
            if score >= 7:
                scored.append(lead_id)
    await message.answer(
        f"✅ Готово. Собрано: {len(leads)}, новых: {new_count}, "
        f"горячих (7+): {len(scored)}"
    )
    for lead_id in scored[:10]:
        lead = db.get_lead(lead_id)
        await message.answer(_lead_card(lead), parse_mode="HTML",
                             reply_markup=_lead_kb(lead_id))


@dp.message(Command("top"))
async def cmd_top(message: Message) -> None:
    if not _is_manager(message):
        return
    leads = db.top_unprocessed(5)
    if not leads:
        await message.answer("Необработанных лидов нет. Запусти /scan")
        return
    for lead in leads:
        await message.answer(_lead_card(lead), parse_mode="HTML",
                             reply_markup=_lead_kb(lead["id"]))


@dp.callback_query(F.data.startswith("offer:"))
async def cb_offer(query: CallbackQuery) -> None:
    if not _is_manager(query):
        return
    lead_id = int(query.data.split(":")[1])
    lead = db.get_lead(lead_id)
    if lead and lead["ai_offer"]:
        await query.message.answer(
            f"📝 <b>Черновик первого сообщения для «{lead['name']}»</b>\n"
            f"<i>(проверь и отправь вручную)</i>\n\n{lead['ai_offer']}",
            parse_mode="HTML",
        )
    await query.answer()


@dp.callback_query(F.data.startswith("st:"))
async def cb_status(query: CallbackQuery) -> None:
    if not _is_manager(query):
        return
    _, lead_id, status = query.data.split(":", 2)
    db.set_status(int(lead_id), status)
    lead = db.get_lead(int(lead_id))
    await query.message.edit_text(_lead_card(lead), parse_mode="HTML",
                                  reply_markup=_lead_kb(lead["id"]))
    await query.answer(f"Статус: {status}")


async def main() -> None:
    db.init_db()
    logger.info("Lead Scout bot запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
