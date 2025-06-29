import os
import logging
import asyncio
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = None  # збережемо id чату після /start

def parse_rada():
    url = "https://zakon.rada.gov.ua/laws/latest"
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select(".law-item")[:5]
    res = []
    for it in items:
        title = it.select_one(".title").get_text(strip=True)
        href = "https://zakon.rada.gov.ua" + it.a["href"]
        date = it.select_one(".date").get_text(strip=True)
        if any(w in title.lower() for w in ["оборон", "військ"]):
            res.append((title, href, date))
    return res

def parse_liga():
    res = {"defense": [], "energy": []}
    for tag, cat in [("oboronna", "defense"), ("vidnovlyuvana-energetika", "energy")]:
        url = f"https://www.liga.net/ua/tag/{tag}"
        resp = requests.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        for el in soup.select(".news-list .title")[:3]:
            t = el.get_text(strip=True)
            l = el.a["href"]
            res[cat].append((t, l))
    return res

def build_digest():
    lines = ["📰 *Дайджест тижня — Оборонка та Зелена енергія*\n"]
    rada = parse_rada()
    if rada:
        lines.append("⚙️ *Оборонна промисловість (ВР):*")
        for t, l, d in rada:
            lines.append(f"• {t} ({d})\n    📌 [Джерело]({l})")
    liga = parse_liga()
    if liga["defense"]:
        lines.append("\n🛡 *Оборонка (liga.net):*")
        for t, l in liga["defense"]:
            lines.append(f"• {t}\n    📌 [Джерело]({l})")
    if liga["energy"]:
        lines.append("\n🌱 *Відновлювана енергія (liga.net):*")
        for t, l in liga["energy"]:
            lines.append(f"• {t}\n    📌 [Джерело]({l})")
    lines.append("\nНаступне оновлення — у понеділок.")
    return "\n".join(lines)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID
    CHAT_ID = update.effective_chat.id
    await update.message.reply_text("Бот активовано. Щопонеділка буде дайджест.")
    logging.info(f"Activated chat_id={CHAT_ID}")

async def digest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = build_digest()
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)
    logging.info("Manual digest sent")

async def send_digest(bot: Bot):
    if CHAT_ID:
        text = build_digest()
        await bot.send_message(chat_id=CHAT_ID, text=text,
                               parse_mode="Markdown", disable_web_page_preview=True)
        logging.info("Digest sent")
    else:
        logging.warning("No CHAT_ID registered")

async def main():
    logging.basicConfig(level=logging.INFO)
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("digest", digest))

    scheduler = AsyncIOScheduler(timezone="Europe/Kyiv")
    scheduler.add_job(lambda: asyncio.create_task(send_digest(app.bot)),
                      trigger="cron", day_of_week="mon", hour=9, minute=0)
    scheduler.start()

    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())
