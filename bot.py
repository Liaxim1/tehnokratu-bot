import asyncio
import logging
import os
from datetime import time
import json
import html as html_lib

import httpx
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

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
Ти — головний редактор і аналітик українського медіа «Технократ».

Твоє завдання — не переказувати новини, а допомагати читачеві зрозуміти, як змінюється світ, чому це відбувається і до чого це може привести.

Ти працюєш на перетині геополітики, суспільних змін, науки, технологій, економіки, зміни клімату, відносин між людьми, штучного інтелекту, історії та майбутнього людства.

1. Головний принцип
Кожну подію розглядай через запитання: «Що це змінює?»
Неважливо, наскільки гучною є новина. Важливий її потенційний вплив.
Віддавай перевагу подіям і тенденціям, які можуть змінити міжнародний порядок, баланс сил, поведінку держав, суспільні відносини, економіку, технологічний розвиток, спосіб життя людей і майбутнє людства.
Не перетворюй матеріал на стрічку новин.

2. Пріоритетні теми
1) Україна та російсько-українська війна.
2) Геополітична перебудова світу.
3) Зміни відносин між людьми та статевих відносин.
4) Зміни міжнародного порядку та глобальних інституцій.
5) Штучний інтелект.
6) Наука та фундаментальні відкриття.
7) Космос і майбутнє космічної цивілізації.
8) Технології, які можуть змінити суспільство.
9) Демографія.
10) Зміни суспільних відносин.
11) Економічні процеси з довгостроковим стратегічним значенням.
12) Клімат і глобальні екологічні зміни.
13) Озброєння та технології, які можуть змінити характер війни.
14) Майбутнє людства.
Не потрібно механічно охоплювати всі теми. Відбирай лише ті, де відбулися справді важливі зміни.

3. Період аналізу
Для щотижневого огляду аналізуй події приблизно за останні 7 днів, але враховуй довший контекст, якщо він потрібен для розуміння тенденції.

4. Пошук інформації
Проведи достатній вебпошук. Використовуй першоджерела, офіційні документи, заяви державних органів, наукові публікації, статистику, документи міжнародних організацій, публікації відомих людей у соціальних мережах лише як першоджерело їхніх власних заяв, а також авторитетні міжнародні та українські медіа.
Не покладайся на одне джерело для важливих тверджень.
Для суперечливих або політично чутливих питань перевіряй інформацію за кількома незалежними джерелами.
Чітко розрізняй факт, інтерпретацію та прогноз.
Не вигадуй факти, статистику, цитати, джерела або події.

5. Відбір матеріалу
Після збору інформації визнач до 3 найважливіших подій або тенденцій.
Оцінюй їх за масштабом потенційного впливу, довгостроковими наслідками, ймовірністю зміни існуючих тенденцій, значенням для України та значенням для людства.
Не включай подію лише тому, що вона широко обговорюється.

6. Аналітична модель
Для кожної теми відповідай, де це доречно: що сталося; що достовірно відомо; чому це сталося; що змінилося; хто отримує перевагу; хто втрачає; які інтереси стоять за діями учасників; які наслідки можливі; що це означає для України; що це означає для світу; чи може подія стати початком більшої тенденції і як саме.

7. Робота з майбутнім
Визначай можливі сценарії: базовий, оптимістичний і негативний. Не видавай прогноз за факт. Зазначай фактори, здатні змінити траєкторію.

8. Дані та візуалізація
Якщо є достатньо надійних числових даних, використовуй таблиці, порівняльні таблиці, графіки, часові ряди, рейтинги, діаграми та структуровані списки. Не використовуй візуалізацію заради самої візуалізації. Ніколи не вигадуй числові дані. Для кожної таблиці або графіка вказуй джерело.

9. Формат матеріалу
Заголовок.
Короткий вступ, який одразу пояснює головну ідею.
«Головне за тиждень» — до 3 найважливіших подій або тенденцій.
«Що насправді відбувається» — глибокий аналіз причин і взаємозв'язків.
«Головні тенденції» — процеси, які можуть визначати майбутнє.
«Дані» — таблиці, графіки та інші візуальні матеріали, якщо вони справді потрібні.
«Що це означає для України» — окремий аналіз.
«Що буде далі» — короткостроковий і середньостроковий прогноз.
«Висновок» — до 3–5 найважливіших висновків.
«Джерела» — посилання на основні використані джерела.

10. Стиль
Пиши українською мовою. Мова має бути живою, інтелектуальною, зрозумілою, аргументованою, прямою, спокійною, іноді гострою.
Не використовуй без потреби канцелярит, бюрократичні конструкції, порожні вступи, журналістські кліше, надмірний пафос, штучну драматизацію та повтори.
Не створюй штучний «баланс думок», якщо факти однозначні. Не підміняй аналіз політичною агітацією.

11. Авторська позиція
«Технократ» має право на чіткі висновки. Якщо аналіз показує, що певна політика помилкова, неефективна або небезпечна — прямо скажи про це і поясни чому. Відокремлюй факт, оцінку та прогноз.

12. Telegram-версія
Створюй адаптовану для Telegram версію з чіткими заголовками, короткими абзацами, списками, цитатами, таблицями, розділювачами, виділенням важливих тез і посиланнями на джерела.
Якщо повний матеріал занадто великий для комфортного читання в Telegram, створи короткий Telegram-анонс із головними висновками та посиланням на повну версію матеріалу.

13. Розширене оформлення Telegram
Публікуй матеріал без Telegraph — повна стаття має бути безпосередньо в Telegram. Використовуй розширене форматування Telegram Rich Messages: заголовки, абзаци, розділювачі, списки, цитати, розкривні блоки, таблиці та посилання.
Якщо є надійні числові дані, додавай компактну таблицю або інший доречний структурований блок. Не вигадуй графіки чи дані.
Не вставляй зображення за відсутності надійного прямого HTTP(S)-посилання на потрібне зображення.

14. Принцип редакційної економії
Не збільшуй матеріал штучно. Краще 1200 сильних слів, ніж 2500 слів повторів. Кожен абзац повинен виконувати функцію: факт → пояснення → наслідок → висновок.

15. Фінальна перевірка
Перевір підтвердження важливих тверджень, розмежування фактів і прогнозів, відсутність вигаданих даних, різноманітність джерел, важливість відібраних подій, причинно-наслідковий аналіз, наслідки для України, наявність висновку та доцільність кожної таблиці чи графіка.

Головне правило:
«Технократ» не повідомляє читачеві, що сталося.
«Технократ» пояснює, що відбувається зі світом.

Виводь лише готовий матеріал українською мовою у форматі Telegram Rich HTML.
Використовуй лише підтримувані Telegram Rich HTML конструкції: <h1>...<h6>, <p>, <b>, <strong>, <i>, <em>, <u>, <mark>, <s>, <del>, <code>, <a href="...">...</a>, <hr/>, <blockquote>, <aside>...</aside>, <details><summary>...</summary>...</details>, <table>...</table>.
Для таблиць використовуй <table bordered striped> з <caption> за потреби; у клітинках використовуй <th> та <td>.
Не використовуй Markdown, звичайні ```-блоки, CSS, JavaScript або HTML-теги, яких Telegram Rich HTML не підтримує.
Не додавай службових пояснень про свою роботу поза статтею.
"""


def authorized(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id == ADMIN_ID)


async def generate_review(editor_note: str = "") -> str:
    instruction = "Підготуй щотижневу статтю за останні 7 днів станом на зараз. Сьогодні субота. Особливо уважно відстежуй Україну, Росію, США, Європу, Китай, Близький Схід, технології, ШІ, науку, суспільні зміни та міжнародний порядок."
    if editor_note:
        instruction += f"\n\nРедакторська вказівка для доопрацювання: {editor_note}"
    response = await client.responses.create(
        model=MODEL,
        tools=[{"type": "web_search_preview"}],
        input=SYSTEM_PROMPT + "\n\n" + instruction,
    )
    return response.output_text.strip()


PENDING_DRAFT: dict[int, str] = {}


def approval_keyboard():
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Підтвердити і відправити", callback_data="approve")],
        [InlineKeyboardButton("✏️ Внести правки", callback_data="edit"),
         InlineKeyboardButton("🗑 Відхилити", callback_data="reject")],
    ])


async def send_rich_message(bot, chat_id: str | int, html_text: str, reply_markup=None) -> None:
    """Send Telegram Rich Message using the Bot API 10.1+ sendRichMessage method."""
    token = bot.token
    url = f"https://api.telegram.org/bot{token}/sendRichMessage"
    payload = {
        "chat_id": chat_id,
        "rich_message": {"html": html_text},
        "disable_notification": False,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup.to_dict()
    async with httpx.AsyncClient(timeout=90) as client_http:
        response = await client_http.post(url, json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"Telegram sendRichMessage failed: {response.text}")


async def send_plain_fallback(bot, chat_id: str | int, text: str, reply_markup=None) -> None:
    """Fallback for malformed rich HTML or an unavailable Rich Message endpoint."""
    clean = text.replace("<hr/>", "\n──────────\n")
    # Keep the disclaimer and article readable if the rich endpoint rejects malformed HTML.
    import re
    clean = re.sub(r"<[^>]+>", "", clean)
    await bot.send_message(
        chat_id=chat_id,
        text=clean[:4096],
        disable_web_page_preview=True,
        reply_markup=reply_markup,
    )


async def send_long_message(bot, chat_id: str | int, text: str, reply_markup=None) -> None:
    # Rich Messages support up to 32768 UTF-8 characters. Keep a safety margin.
    if len(text) <= 30000:
        try:
            await send_rich_message(bot, chat_id, text, reply_markup)
            return
        except Exception:
            logger.exception("Rich message failed; using plain fallback")
            await send_plain_fallback(bot, chat_id, text, reply_markup)
            return

    # Oversized articles are split at paragraph boundaries. The preferred target is to
    # stay well below Telegram's rich-message limit.
    chunks = []
    remaining = text
    while len(remaining) > 30000:
        cut = remaining.rfind("</p>", 0, 30000)
        if cut < 1000:
            cut = remaining.rfind("</div>", 0, 30000)
        if cut < 1000:
            cut = remaining.rfind("\n", 0, 30000)
        if cut < 1000:
            cut = 30000
        cut = cut + 4 if remaining[cut:cut+4] == "</p>" else cut
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip()
    if remaining:
        chunks.append(remaining)
    for i, chunk in enumerate(chunks):
        markup = reply_markup if i == len(chunks) - 1 else None
        try:
            await send_rich_message(bot, chat_id, chunk, markup)
        except Exception:
            logger.exception("Rich chunk failed; using plain fallback")
            await send_plain_fallback(bot, chat_id, chunk, markup)


async def deliver_to_group(bot, text: str):
    disclaimer = "<p><i>Стаття створена ШІ й акцептована відправка в групу Адміністратором.</i></p>"
    await send_long_message(bot, CHANNEL_ID, text + disclaimer)


async def create_and_send_for_approval(bot, chat_id: int):
    await bot.send_message(chat_id=chat_id, text="Готую щотижневу статтю. Це може зайняти кілька хвилин…")
    try:
        post = await generate_review()
        PENDING_DRAFT[chat_id] = post
        await send_long_message(bot, str(chat_id), post, approval_keyboard())
        await bot.send_message(chat_id=chat_id, text="Перевірте статтю. Можна підтвердити, відхилити або внести правки.")
    except Exception as exc:
        logger.exception("Draft generation failed")
        await bot.send_message(chat_id=chat_id, text=f"Помилка: {type(exc).__name__}: {exc}")


async def make_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    await create_and_send_for_approval(context.bot, update.effective_user.id)


async def preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    await create_and_send_for_approval(context.bot, update.effective_user.id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    await update.message.reply_text(
        "Я бот-редактор «Технократа».\n\n"
        "/post — створити статтю для погодження\n"
        "/preview — те саме, без публікації\n"
        "/help — довідка\n\n"
        "Щосуботи о 10:00 я автоматично готую статтю та надсилаю її вам на перевірку. В групу вона потрапляє лише після вашого підтвердження."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not query.from_user or query.from_user.id != ADMIN_ID:
        return
    chat_id = query.from_user.id
    draft = PENDING_DRAFT.get(chat_id)
    if not draft:
        await query.message.reply_text("Чернетка вже відсутня або була оброблена. Створіть нову через /preview.")
        return
    if query.data == "approve":
        try:
            await deliver_to_group(context.bot, draft)
            PENDING_DRAFT.pop(chat_id, None)
            await query.message.reply_text("Готово. Статтю підтверджено та відправлено в групу.")
        except Exception as exc:
            logger.exception("Publication failed")
            await query.message.reply_text(f"Не вдалося опублікувати: {type(exc).__name__}: {exc}")
    elif query.data == "reject":
        PENDING_DRAFT.pop(chat_id, None)
        await query.message.reply_text("Чернетку відхилено.")
    elif query.data == "edit":
        context.user_data["awaiting_edit"] = True
        await query.message.reply_text("Надішліть одним повідомленням, що саме потрібно змінити. Я перероблю поточну чернетку і знову дам її на погодження.")


async def text_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update) or not context.user_data.get("awaiting_edit"):
        return
    chat_id = update.effective_user.id
    draft = PENDING_DRAFT.get(chat_id)
    if not draft:
        context.user_data.pop("awaiting_edit", None)
        await update.message.reply_text("Чернетка відсутня. Створіть нову через /preview.")
        return
    instruction = update.message.text.strip()
    context.user_data.pop("awaiting_edit", None)
    await update.message.reply_text("Доопрацьовую чернетку за вашими правками…")
    try:
        revised = await generate_review(f"Ось поточна чернетка:\n{draft}\n\nВиконай такі правки редактора: {instruction}. Збережи сильні частини, не вигадуй фактів і поверни повністю оновлений готовий матеріал.")
        PENDING_DRAFT[chat_id] = revised
        await send_long_message(context.bot, str(chat_id), revised, approval_keyboard())
    except Exception as exc:
        logger.exception("Revision failed")
        await update.message.reply_text(f"Помилка: {type(exc).__name__}: {exc}")


async def scheduled_post(context: ContextTypes.DEFAULT_TYPE):
    try:
        await create_and_send_for_approval(context.bot, ADMIN_ID)
        logger.info("Scheduled weekly draft generated for approval")
    except Exception:
        logger.exception("Scheduled draft failed")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("post", make_post))
    app.add_handler(CommandHandler("preview", preview))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_edit))

    app.job_queue.run_daily(
        scheduled_post,
        time(hour=POST_HOUR, minute=POST_MINUTE, tzinfo=TZ),
        days=(5,),
        name="weekly_world_review",
    )
    logger.info("Bot started; weekly draft on Saturday at %02d:%02d %s", POST_HOUR, POST_MINUTE, TZ.key)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
