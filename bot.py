import asyncio
import logging
import os
from datetime import time
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
POST_HOUR = int(os.getenv("POST_HOUR", "9"))
POST_MINUTE = int(os.getenv("POST_MINUTE", "0"))
TZ = ZoneInfo(os.getenv("TIMEZONE", "Europe/Kyiv"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Ти — редактор авторського українського Telegram-каналу про політику, геополітику,
війну, майбутнє людства, ШІ, науку, космос, історію, суспільство, культуру та
глобальні зміни.

Твоє завдання — щодня визначати найважливіші події та тенденції у світі й
перетворювати їх на сильний авторський допис українською мовою.

Вимоги:
- не роби механічний перелік новин;
- обирай 3–5 справді важливих сюжетів;
- пояснюй, чому вони важливі та що можуть змінити;
- відокремлюй факти від прогнозів та інтерпретацій;
- не вигадуй фактів;
- використовуй актуальні джерела через вебпошук;
- перевага Reuters, AP, BBC, FT, WSJ, NYT, The Economist, Nature, Science,
  офіційним державним і міжнародним джерелам та першоджерелам;
- українська мова, живий але професійний стиль;
- без канцеляриту та порожніх фраз;
- допускається гостра оцінка, але вона має бути аргументованою;
- не використовуй російську мову, якщо це не назва власної назви;
- завершуй блоком «Що це означає» з 3–5 короткими висновками.

Формат:
Заголовок

Короткий вступ — 2–4 речення.

Далі 3–5 тематичних блоків із підзаголовками.

Наприкінці: «Що це означає».

Обсяг: приблизно 900–1500 слів.
"""


def authorized(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id == ADMIN_ID)


async def generate_review() -> str:
    response = await client.responses.create(
        model=MODEL,
        tools=[{"type": "web_search_preview"}],
        input=SYSTEM_PROMPT + "\nПідготуй огляд за останні 24 години станом на зараз. Особливо уважно відстежуй Україну, Росію, США, Європу, Китай, Близький Схід, технології, ШІ, науку та зміни міжнародного порядку.",
    )
    return response.output_text.strip()


async def send_long_message(bot, chat_id: str, text: str) -> None:
    # Telegram limits text messages to 4096 characters.
    chunks = []
    while len(text) > 3900:
        cut = text.rfind("\n", 0, 3900)
        if cut < 1000:
            cut = 3900
        chunks.append(text[:cut])
        text = text[cut:].lstrip()
    chunks.append(text)
    for chunk in chunks:
        await bot.send_message(chat_id=chat_id, text=chunk, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def make_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    await update.message.reply_text("Готую огляд і допис…")
    try:
        post = await generate_review()
        await send_long_message(context.bot, CHANNEL_ID, post)
        await update.message.reply_text("Готово: допис опубліковано в каналі.")
    except Exception as exc:
        logger.exception("Generation/publication failed")
        await update.message.reply_text(f"Помилка: {type(exc).__name__}: {exc}")


async def preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    await update.message.reply_text("Готую попередній перегляд…")
    try:
        post = await generate_review()
        await send_long_message(context.bot, str(update.effective_chat.id), post)
    except Exception as exc:
        logger.exception("Preview failed")
        await update.message.reply_text(f"Помилка: {type(exc).__name__}: {exc}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    await update.message.reply_text(
        "Я бот для вашого каналу.\n\n"
        "/post — створити й опублікувати огляд\n"
        "/preview — створити огляд без публікації\n"
        "/help — довідка"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def scheduled_post(context: ContextTypes.DEFAULT_TYPE):
    try:
        post = await generate_review()
        await send_long_message(context.bot, CHANNEL_ID, post)
        logger.info("Scheduled post published")
    except Exception:
        logger.exception("Scheduled post failed")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("post", make_post))
    app.add_handler(CommandHandler("preview", preview))

    app.job_queue.run_daily(
        scheduled_post,
        time(hour=POST_HOUR, minute=POST_MINUTE, tzinfo=TZ),
        name="daily_world_review",
    )
    logger.info("Bot started; daily publication at %02d:%02d %s", POST_HOUR, POST_MINUTE, TZ.key)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
