"""Операции с SQLite базой лидов (организации Краснодара)."""

from __future__ import annotations

import logging
import shutil
import sqlite3
from datetime import datetime
from typing import Optional

from config import DB_PATH

logger = logging.getLogger(__name__)

STATUSES = ["новый", "в работе", "отправлено КП", "встреча", "клиент", "отказ", "не подходит"]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dgis_id TEXT UNIQUE,
                name TEXT,
                niche TEXT,
                address TEXT,
                phone TEXT,
                website TEXT,
                socials TEXT,
                rating REAL,
                reviews_count INTEGER,
                has_online_booking INTEGER DEFAULT 0,
                raw_json TEXT,
                ai_score INTEGER,
                ai_summary TEXT,
                ai_offer TEXT,
                status TEXT DEFAULT 'новый',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        logger.info("База данных инициализирована: %s", DB_PATH)
    finally:
        conn.close()


def upsert_lead(data: dict) -> tuple[int, bool]:
    """Сохранить лид. Возвращает (id, is_new)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM leads WHERE dgis_id = ?", (data["dgis_id"],)
        ).fetchone()
        if row:
            conn.execute(
                """UPDATE leads SET name=?, niche=?, address=?, phone=?, website=?,
                   socials=?, rating=?, reviews_count=?, raw_json=?,
                   updated_at=CURRENT_TIMESTAMP WHERE dgis_id=?""",
                (data["name"], data["niche"], data.get("address"), data.get("phone"),
                 data.get("website"), data.get("socials"), data.get("rating"),
                 data.get("reviews_count"), data.get("raw_json"), data["dgis_id"]),
            )
            conn.commit()
            return row["id"], False
        cur = conn.execute(
            """INSERT INTO leads (dgis_id, name, niche, address, phone, website,
               socials, rating, reviews_count, raw_json)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (data["dgis_id"], data["name"], data["niche"], data.get("address"),
             data.get("phone"), data.get("website"), data.get("socials"),
             data.get("rating"), data.get("reviews_count"), data.get("raw_json")),
        )
        conn.commit()
        return cur.lastrowid, True
    finally:
        conn.close()


def save_ai_result(lead_id: int, score: int, summary: str, offer: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE leads SET ai_score=?, ai_summary=?, ai_offer=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (score, summary, offer, lead_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_status(lead_id: int, status: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE leads SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, lead_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_lead(lead_id: int) -> Optional[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    finally:
        conn.close()


def list_leads(niche: str = "", status: str = "", min_score: int = 0,
               search: str = "") -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        query = "SELECT * FROM leads WHERE 1=1"
        params: list = []
        if niche:
            query += " AND niche=?"
            params.append(niche)
        if status:
            query += " AND status=?"
            params.append(status)
        if min_score:
            query += " AND ai_score >= ?"
            params.append(min_score)
        if search:
            query += " AND (name LIKE ? OR address LIKE ? OR phone LIKE ?)"
            params += [f"%{search}%"] * 3
        query += " ORDER BY COALESCE(ai_score, 0) DESC, created_at DESC"
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


def top_unprocessed(limit: int = 5) -> list[sqlite3.Row]:
    """Лучшие необработанные лиды для дайджеста менеджеру."""
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM leads WHERE status='новый' AND ai_score IS NOT NULL "
            "ORDER BY ai_score DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()


def backup_db() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = DB_PATH.parent / "backups" / f"leads_backup_{ts}.db"
    dest.parent.mkdir(exist_ok=True)
    shutil.copy2(DB_PATH, dest)
    return str(dest)
