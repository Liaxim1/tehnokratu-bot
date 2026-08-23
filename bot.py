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
POST_HOUR = int(os.getenv("POST_HOUR", "10"))
POST_MINUTE = int(os.getenv("POST_MINUTE", "0"))
TZ = ZoneInfo(os.getenv("TIMEZONE", "Europe/Kyiv"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = 'Ти — головний редактор і аналітик українського медіа «Технократ».\nТвоє завдання — не переказувати новини, а пояснювати, як змінюється світ, чому це відбувається і до чого це може привести в майбутньому.\n\nГоловний принцип\n\nШукай не найгучніші новини, а найважливіші зміни.\n\nГоловне питання:\n«Що ця подія може змінити в майбутньому?»\n\nПеревагу надавай подіям, які можуть впливати на майбутнє людства, науку, штучний інтелект (ШІ), технології, космос, енергетику, клімат, демографію, суспільні відносини, відносини між чоловіками та жінками, економіку та геополітичний порядок.\n\nОсобливо звертай увагу на невеликі сьогодні події, які можуть стати великими тенденціями завтра.\n\nВійна\n\nРосійсько-українська війна — лише одна з тем.\n\nНе включай її до кожного огляду автоматично. Пиши про неї лише тоді, коли відбулися суттєві стратегічні зміни, які можуть вплинути на Україну, Європу, міжнародний порядок або майбутнє війни.\n\nНе дозволяй війні витісняти важливіші зміни у науці, технологіях, ШІ, космосі, суспільстві чи інших сферах.\n\nВідбір\n\nПроаналізуй приблизно останні 7 днів і вибери від 1 до 3 найважливіших тем.\n\nНе створюй додаткові теми штучно.\n\nОцінюй їх за:\n- впливом на майбутнє;\n- масштабом можливих змін;\n- довгостроковими наслідками;\n- значенням для людства;\n- значенням для України.\n\nДжерела\n\nПроводь достатній вебпошук.\n\nВикористовуй першоджерела, офіційні документи, наукові публікації, статистику, авторитетні українські та міжнародні медіа, а також дописи відомих людей у соціальних мережах (тільки якщо ці люди можуть бути першоджерелами цих новин або подій).\n\nВикористовуй і українські, і міжнародні джерела, оцінюючи їх за якістю, а не за країною походження.\n\nДля важливих або суперечливих тверджень використовуй декілька незалежних джерел.\n\nНе вигадуй фактів, статистики, цитат або джерел.\n\nАналіз\n\nДля кожної теми поясни:\nЩо сталося?\nЧому це сталося?\nЩо змінилося?\nЧому це важливо?\nХто отримує перевагу?\nЯкі можливі наслідки?\nЩо це означає для України та світу?\nЧи може це стати початком більшої тенденції?\n\nЧітко відокремлюй факти, власний аналіз та прогноз.\n\nПрогнози подавай як можливі сценарії, а не як встановлені факти.\n\nСтиль\n\nПиши українською.\n\nСтиль — живий, інтелектуальний, зрозумілий, аргументований і прямий.\n\nМова повинна бути живою та природною, без шаблонності.\nУ доречних місцях допускається гостра, різка й провокативна подача, якщо вона підсилює аргумент і випливає з аналізу.\nГострота не повинна перетворюватися на образи, дешеву сенсаційність або штучну драматизацію.\n\nНе використовуй зайвий пафос, канцелярит, журналістські кліше та повтори.\n\nНе створюй штучного «балансу думок», якщо факти дозволяють зробити однозначний висновок.\n\nНе перетворюй матеріал на стрічку новин.\n\nНе використовуй як заголовок або назву розділу формулювання «Аналіз Технократа» чи подібні саморекламні назви. Стаття сама є аналітичним матеріалом «Технократа».\n\nСтруктура\n\nМатеріал повинен містити:\nЗаголовок\nКороткий вступ\nГоловне за тиждень\nАналіз вибраних тем\nЩо це означає для України — якщо тема має суттєве значення для України.\nЩо буде далі — якщо прогноз справді має цінність.\nВисновок\nДжерела\n\nВикористовуй таблиці, графіки та інші візуальні матеріали лише тоді, коли вони реально допомагають зрозуміти тему.\n\nНе збільшуй матеріал штучно.\n\nКраще одна справді важлива тема з глибоким аналізом, ніж три поверхневі новини.\n\nФінальне правило\n\nНе пиши про те, що було важливим цього тижня. Пиши про те, що сталося цього тижня і може виявитися важливим для майбутнього.\n\nНе шукай новини про майбутнє. Шукай майбутнє в новинах.'


def authorized(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id == ADMIN_ID)


async def generate_review(editor_note: str = "") -> str:
    instruction = "Підготуй щотижневу статтю за останні 7 днів станом на зараз. Сьогодні субота. Особливо уважно відстежуй Україну, Росію, США, Європу, Китай, Близький Схід, технології, ШІ, науку, суспільні зміни та міжнародний порядок."
    if editor_note:
        instruction += f"\n\nРедакторська вказівка для доопрацювання: {editor_note}"
    response = await client.responses.create(
        model=MODEL,
        tools=[{"type": "web_search"}],
        input=SYSTEM_PROMPT + "\n\n" + instruction,
    )
    return response.output_text.strip()


PENDING_DRAFT: dict[int, str] = {}


async def generate_answer(question: str) -> str:
    instruction = f"""Це окреме редакційне питання, а не щотижневий огляд.
Відповідай безпосередньо на питання користувача, провівши достатній вебпошук.
Не вигадуй фактів. Для важливих тверджень використовуй кілька незалежних джерел.
Чітко відокремлюй встановлені факти від власного аналізу та прогнозів.
Не намагайся штучно прив'язати відповідь до тижневого огляду або до війни, якщо це не має стосунку до питання.
Пиши українською, живою, природною, інтелектуальною та зрозумілою мовою. За доречності допускається гостра й пряма подача.
Не називай розділи «Аналіз Технократа».
Формат відповіді обирай відповідно до питання: коротка відповідь, глибокий розбір, порівняння, сценарії, таблиця тощо.

Питання користувача:
{question}"""
    response = await client.responses.create(
        model=MODEL,
        tools=[{"type": "web_search"}],
        input=SYSTEM_PROMPT + "\n\n" + instruction,
    )
    return response.output_text.strip()

async def revise_draft(draft: str, instruction: str) -> str:
    prompt = f"""Ти редагуєш уже підготовлений матеріал «Технократа».

Користувач просить внести такі зміни:
{instruction}

Відредагуй текст відповідно до прохання.
Зберігай сильні частини початкового матеріалу, якщо користувач не просить їх змінювати.
Не скорочуй матеріал без потреби.
Не додавай вигаданих фактів, цифр, цитат або джерел.
Якщо для зміни потрібна нова фактична інформація, перевір її вебпошуком.
Зберігай українську мову, живий, інтелектуальний, зрозумілий і прямий стиль; за доречності допускається гостра подача.
Не називай жоден розділ «Аналіз Технократа».
Поверни повністю оновлений текст статті, а не перелік внесених змін.

ПОЧАТКОВИЙ ТЕКСТ:
{draft}
"""
    response = await client.responses.create(
        model=MODEL,
        tools=[{"type": "web_search"}],
        input=SYSTEM_PROMPT + "\n\n" + prompt,
    )
    return response.output_text.strip()



def approval_keyboard():
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Підтвердити і відправити", callback_data="approve")],
        [InlineKeyboardButton("✏️ Внести правки", callback_data="revise"),
         InlineKeyboardButton("📝 Ввести свій текст", callback_data="edit")],
    ])


def markdown_to_rich_html(text: str) -> str:
    """Convert the model's Markdown into safe Telegram Rich Message HTML."""
    import re
    import html as _html

    # If the model already returned HTML, keep it as-is.
    if re.search(r"<h[1-6][^>]*>|<p[^>]*>|<table[^>]*>", text, re.I):
        return text

    lines = text.replace("\r\n", "\n").split("\n")
    out = []
    in_ul = False
    in_ol = False
    in_quote = False
    i = 0

    def inline(s: str) -> str:
        s = _html.escape(s, quote=False)
        # Markdown links first.
        s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
        # Bare URLs.
        s = re.sub(r'(?<![\"=])(https?://[^\s<]+)', r'<a href="\1">\1</a>', s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"__([^_]+)__", r"<b>\1</b>", s)
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", s)
        s = re.sub(r"(?<!_)_([^_]+)_(?!_)", r"<i>\1</i>", s)
        return s

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    def close_quote():
        nonlocal in_quote
        if in_quote:
            out.append("</blockquote>")
            in_quote = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            close_lists(); close_quote(); i += 1; continue

        # Markdown table.
        if i + 1 < len(lines) and "|" in line and re.match(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", lines[i+1]):
            close_lists(); close_quote()
            def cells(x):
                x=x.strip().strip("|")
                return [c.strip() for c in x.split("|")]
            headers=cells(line)
            out.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in headers) + "</tr></thead><tbody>")
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                row=cells(lines[i])
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>")
                i += 1
            out.append("</tbody></table>")
            continue

        m = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if m:
            close_lists(); close_quote()
            level=min(len(m.group(1)), 4)
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1; continue

        if re.match(r"^\s*(---+|___+|\*\s*\*\s*\*+)\s*$", line):
            close_lists(); close_quote(); out.append("<hr/>"); i += 1; continue

        m = re.match(r"^\s*[-*+]\s+(.+)$", line)
        if m:
            close_quote()
            if not in_ul:
                if in_ol: out.append("</ol>"); in_ol=False
                out.append("<ul>"); in_ul=True
            out.append(f"<li>{inline(m.group(1))}</li>")
            i += 1; continue

        m = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        if m:
            close_quote()
            if not in_ol:
                if in_ul: out.append("</ul>"); in_ul=False
                out.append("<ol>"); in_ol=True
            out.append(f"<li>{inline(m.group(1))}</li>")
            i += 1; continue

        m = re.match(r"^\s*>\s?(.*)$", line)
        if m:
            close_lists()
            if not in_quote:
                out.append("<blockquote>"); in_quote=True
            out.append(inline(m.group(1)) + "<br/>")
            i += 1; continue

        close_lists(); close_quote()
        out.append(f"<p>{inline(stripped)}</p>")
        i += 1

    close_lists(); close_quote()
    return "".join(out)


async def send_rich_message(bot, chat_id: str | int, html_text: str, reply_markup=None) -> None:
    """Send Telegram Rich Message using the Bot API 10.1+ sendRichMessage method."""
    html_text = markdown_to_rich_html(html_text)
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
    # The disclaimer is inserted by the bot, not by the model.
    # It is placed directly under the first title/heading block.
    disclaimer = "<p><i>Стаття створена ШІ й акцептована відправка в групу Адміністратором.</i></p>"
    if text:
        import re
        match = re.search(r"(<h[1-6][^>]*>.*?</h[1-6]>)", text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            insert_at = match.end()
            text = text[:insert_at] + disclaimer + text[insert_at:]
        else:
            # Fallback if the model did not produce an HTML heading.
            text = disclaimer + text
    await send_long_message(bot, CHANNEL_ID, text)



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


async def done_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    if not context.user_data.get("manual_edit"):
        await update.message.reply_text("Зараз немає режиму ручного введення статті.")
        return
    parts = context.user_data.get("manual_parts", [])
    if not parts:
        await update.message.reply_text("Ви ще не надіслали текст.")
        return

    draft = "\n\n".join(parts).strip()
    user_id = update.effective_user.id
    PENDING_DRAFT[user_id] = draft
    context.user_data.pop("manual_edit", None)
    context.user_data.pop("manual_parts", None)

    await update.message.reply_text("Готово. Ваш текст встановлено як нову чернетку. Перевірте його:")
    await send_long_message(
        context.bot,
        str(user_id),
        draft,
        approval_keyboard(),
    )



async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    user_id = update.effective_user.id
    existed = PENDING_DRAFT.pop(user_id, None) is not None
    context.user_data.pop("revision_edit", None)
    context.user_data.pop("manual_edit", None)
    context.user_data.pop("manual_parts", None)
    context.user_data.pop("awaiting_question", None)
    if existed:
        await update.message.reply_text("Поточну чернетку скасовано. Її не буде опубліковано.")
    else:
        await update.message.reply_text("Активної чернетки немає.")


async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return

    question = " ".join(context.args).strip()
    if not question:
        context.user_data["awaiting_question"] = True
        await update.message.reply_text(
            "Напишіть питання одним повідомленням. Я проведу вебпошук і зроблю окремий аналіз."
        )
        return

    await update.message.reply_text("Шукаю інформацію та готую відповідь…")
    try:
        answer = await generate_answer(question)
        PENDING_DRAFT[update.effective_user.id] = answer
        await send_long_message(
            context.bot,
            str(update.effective_user.id),
            answer,
            approval_keyboard(),
        )
        await update.message.reply_text(
            "Це чернетка аналізу. Можна підтвердити публікацію, внести правки запитом, "
            "повністю замінити текст вручну."
        )
    except Exception as exc:
        logger.exception("Question analysis failed")
        await update.message.reply_text(f"Помилка: {type(exc).__name__}: {exc}")



async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    await update.message.reply_text(
        "Я бот-редактор «Технократа».\n\n"
        "/post — створити статтю для погодження\n"
        "/preview — створити статтю без автоматичної публікації\n"
        "/ask [питання] — окремий аналіз будь-якого питання\n"
        "/done — завершити ручне введення статті\n/cancel — скасувати поточну чернетку\n"
        "/help — довідка\n\n"
        "Щосуботи о 10:00 я автоматично готую статтю та надсилаю її вам на перевірку. "
        "У групу вона потрапляє лише після вашого підтвердження.\n\n"
        "Кнопка «Внести правки» дозволяє дати текстову вказівку, і бот переробить поточну версію. Кнопка «Ввести свій текст» дозволяє повністю замінити чернетку вручну. Якщо матеріал не потрібен, його можна просто не публікувати або скасувати через /cancel. Після /ask результат також стає чернеткою, яку можна редагувати та публікувати."
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
        await query.message.reply_text(
            "Чернетка вже відсутня або була оброблена. Створіть нову через /preview або /ask."
        )
        return

    if query.data == "approve":
        try:
            await deliver_to_group(context.bot, draft)
            PENDING_DRAFT.pop(chat_id, None)
            context.user_data.pop("revision_edit", None)
            context.user_data.pop("manual_edit", None)
            context.user_data.pop("manual_parts", None)
            await query.message.reply_text("Готово. Матеріал підтверджено та відправлено в групу.")
        except Exception as exc:
            logger.exception("Publication failed")
            await query.message.reply_text(f"Не вдалося опублікувати: {type(exc).__name__}: {exc}")

    elif query.data == "revise":
        context.user_data["revision_edit"] = True
        context.user_data.pop("manual_edit", None)
        context.user_data.pop("manual_parts", None)
        await query.message.reply_text(
            "Напишіть одним повідомленням, що саме потрібно змінити. "
            "Наприклад: «Скороти вступ удвічі, додай більше даних про Європу "
            "і зроби висновок гострішим». Я перероблю поточну версію та знову покажу її на погодження."
        )

    elif query.data == "edit":
        context.user_data["manual_edit"] = True
        context.user_data["manual_parts"] = []
        context.user_data.pop("revision_edit", None)
        await query.message.reply_text(
            "Надішліть свій готовий текст замість цієї чернетки. "
            "Можна одним повідомленням або кількома частинами. "
            "Після останньої частини надішліть /done."
        )





async def text_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return

    user_id = update.effective_user.id

    if context.user_data.get("awaiting_question"):
        question = update.message.text.strip()
        context.user_data.pop("awaiting_question", None)
        await update.message.reply_text("Шукаю інформацію та готую відповідь…")
        try:
            answer = await generate_answer(question)
            PENDING_DRAFT[user_id] = answer
            await send_long_message(
                context.bot,
                str(user_id),
                answer,
                approval_keyboard(),
            )
            await update.message.reply_text(
                "Це тепер чернетка аналізу. Її можна підтвердити, відредагувати запитом, "
                "повністю замінити вручну або відхилити."
            )
        except Exception as exc:
            logger.exception("Question analysis failed")
            await update.message.reply_text(f"Помилка: {type(exc).__name__}: {exc}")
        return

    if context.user_data.get("revision_edit"):
        instruction = update.message.text.strip()
        if not instruction:
            return
        draft = PENDING_DRAFT.get(user_id)
        if not draft:
            context.user_data.pop("revision_edit", None)
            await update.message.reply_text("Поточна чернетка вже відсутня. Створіть новий аналіз через /ask.")
            return

        context.user_data.pop("revision_edit", None)
        await update.message.reply_text("Вношу правки та перевіряю фактичні зміни…")
        try:
            revised = await revise_draft(draft, instruction)
            PENDING_DRAFT[user_id] = revised
            await send_long_message(
                context.bot,
                str(user_id),
                revised,
                approval_keyboard(),
            )
        except Exception as exc:
            logger.exception("Draft revision failed")
            await update.message.reply_text(f"Помилка під час редагування: {type(exc).__name__}: {exc}")
        return

    if not context.user_data.get("manual_edit"):
        return

    part = update.message.text
    if not part.strip():
        return
    context.user_data.setdefault("manual_parts", []).append(part)
    count = len(context.user_data["manual_parts"])
    await update.message.reply_text(
        f"Отримала частину {count}. Надішліть наступну частину або /done, якщо це був останній фрагмент."
    )




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
    app.add_handler(CommandHandler("ask", ask_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CommandHandler("done", done_edit))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_edit))

    app.job_queue.run_daily(
        scheduled_post,
        time(hour=POST_HOUR, minute=POST_MINUTE, tzinfo=TZ),
        days=(6,),
        name="weekly_world_review",
    )
    logger.info("Bot started; weekly draft on Saturday at %02d:%02d %s", POST_HOUR, POST_MINUTE, TZ.key)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
