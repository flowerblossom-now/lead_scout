# Lead Scout

> **Prototype / demo project.**

A Telegram bot that hunts for local businesses in Krasnodar that could actually use automation — no website, no online booking, nothing. Built on the same stack as [recruiting_bot](https://github.com/dockergits/recruiting_bot): aiogram + a Flask dashboard + SQLite, with a pinch of AI on top.

`/scan` crawls the 2GIS Places API across a dozen niches — beauty salons, dental clinics, auto repair shops, gyms, cafes, and more. For each business, an AI model scores how much it would benefit from automation (1–10, based on signals like a missing website or no online booking) and drafts a first-contact message. Anything scoring 7+ shows up as a card with status buttons right in the chat, and the full list lives on a dashboard (`http://localhost:5060`) with filters and Excel export.

**Note:** the bot never messages businesses on its own — bulk outreach like that would be spam. It only prepares the shortlist and the draft text; a human sends the actual message.

## Highlights

- Automated lead discovery via the 2GIS Places API, filtered by niche
- AI scoring + drafted outreach message per lead
- Hot leads (7+) delivered as interactive Telegram cards
- Web dashboard with filtering and Excel export

## Run it

```bash
cp .env.example .env   # set BOT_TOKEN, MANAGER_CHAT_IDS, DGIS_API_KEY
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 run.py
```

## Bot commands

- `/scan` — scan all niches, `/scan beauty dental` — only selected ones
- `/top` — top 5 unprocessed leads
- `/niches` — list available niches
