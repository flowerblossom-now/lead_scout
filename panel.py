"""Веб-панель Lead Scout: сканирование 2ГИС, таблица лидов, фильтры, экспорт."""

from __future__ import annotations

import asyncio
import io
import logging
import threading
from functools import wraps

from flask import (
    Flask, jsonify, redirect, render_template, request, send_file, session,
    url_for,
)
from openpyxl import Workbook

import database as db
from ai_scoring import score_lead
from config import (
    NICHES, PANEL_HOST, PANEL_PORT, PANEL_PASSWORD, PANEL_SECRET_KEY, CITY_NAME,
)
from scanner import scan_all

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = PANEL_SECRET_KEY

# Состояние фонового сканирования (один скан за раз)
scan_state = {"running": False, "message": "", "error": ""}


def _run_scan(niche_ids: list[str] | None) -> None:
    """Фоновый поток: сканирование + AI-скоринг новых лидов."""
    try:
        scan_state.update(message="Сканирую 2ГИС…", error="")
        leads = asyncio.run(scan_all(niche_ids))
        new_count = hot = 0
        for i, data in enumerate(leads, 1):
            lead_id, is_new = db.upsert_lead(data)
            if is_new:
                new_count += 1
                scan_state["message"] = f"Оцениваю лиды: {i}/{len(leads)}"
                score, summary, offer = asyncio.run(score_lead(data))
                db.save_ai_result(lead_id, score, summary, offer)
                if score >= 7:
                    hot += 1
        scan_state["message"] = (
            f"Готово: собрано {len(leads)}, новых {new_count}, горячих (7+) {hot}"
        )
    except Exception as exc:
        logger.exception("Ошибка сканирования")
        scan_state["error"] = str(exc)
        scan_state["message"] = ""
    finally:
        scan_state["running"] = False


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("authed"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == PANEL_PASSWORD:
            session["authed"] = True
            return redirect(url_for("index"))
        error = "Неверный пароль"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    niche = request.args.get("niche", "")
    status = request.args.get("status", "")
    min_score = int(request.args.get("min_score") or 0)
    search = request.args.get("q", "")
    leads = db.list_leads(niche, status, min_score, search)
    return render_template(
        "leads.html", leads=leads, niches=NICHES, statuses=db.STATUSES,
        city=CITY_NAME, f_niche=niche, f_status=status,
        f_min_score=min_score, f_search=search,
    )


@app.route("/scan", methods=["POST"])
@login_required
def start_scan():
    if scan_state["running"]:
        return jsonify(scan_state), 409
    niche_ids = request.form.getlist("niches") or None
    scan_state.update(running=True, message="Запуск…", error="")
    threading.Thread(target=_run_scan, args=(niche_ids,), daemon=True).start()
    return jsonify(scan_state)


@app.route("/scan/status")
@login_required
def scan_status():
    return jsonify(scan_state)


@app.route("/lead/<int:lead_id>/status", methods=["POST"])
@login_required
def change_status(lead_id: int):
    db.set_status(lead_id, request.form.get("status", "новый"))
    return redirect(request.referrer or url_for("index"))


@app.route("/export")
@login_required
def export():
    leads = db.list_leads(
        request.args.get("niche", ""), request.args.get("status", ""),
        int(request.args.get("min_score") or 0), request.args.get("q", ""),
    )
    wb = Workbook()
    ws = wb.active
    ws.title = "Лиды"
    ws.append(["Название", "Ниша", "Адрес", "Телефон", "Сайт", "Соцсети",
               "Рейтинг", "Отзывов", "AI-балл", "AI-резюме", "Оффер", "Статус"])
    for lead in leads:
        ws.append([
            lead["name"], lead["niche"], lead["address"], lead["phone"],
            lead["website"], lead["socials"], lead["rating"],
            lead["reviews_count"], lead["ai_score"], lead["ai_summary"],
            lead["ai_offer"], lead["status"],
        ])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="leads.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.route("/backup", methods=["POST"])
@login_required
def backup():
    path = db.backup_db()
    logger.info("Бэкап: %s", path)
    return redirect(url_for("index"))


if __name__ == "__main__":
    db.init_db()
    app.run(host=PANEL_HOST, port=PANEL_PORT)
