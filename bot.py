import os, logging, asyncio
from datetime import datetime
from telegram import Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = None

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

async def start(update, context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID
    CHAT_ID = update.effective_chat.id
    await update.message.reply_text("Бот активовано. Щопонеділка надсилатиметься дайджест.")
    logging.info(f"Activated chat_id={CHAT_ID}")

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

    scheduler = AsyncIOScheduler(timezone="Europe/Kyiv")
    scheduler.add_job(lambda: asyncio.create_task(send_digest(app.bot)),
                      trigger="cron", day_of_week="mon", hour=9, minute=0)
    scheduler.start()

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
