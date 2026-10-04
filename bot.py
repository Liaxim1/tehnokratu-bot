import asyncio
import logging
import os
import re
import json
import html as html_lib
from pathlib import Path

import httpx
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

load_dotenv()

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/telegram/webhook")
SCHEDULE_SECRET = os.getenv("SCHEDULE_SECRET", "")
STATE_DIR = Path(os.getenv("STATE_DIR", "/data"))
STATE_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = STATE_DIR / "state.json"

# Telegram Rich Messages allow up to 32,768 UTF-8 characters. Keep published
# articles at no more than 75% of that ceiling, with a safety margin for links
# and formatting overhead.
MAX_ARTICLE_CHARS = 24500
TARGET_ARTICLE_CHARS = 22000

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = 'Ти — головний редактор і аналітик українського медіа «Технократ».\nТвоє завдання — не переказувати новини, а пояснювати, як змінюється світ, чому це відбувається і до чого це може привести в майбутньому.\n\nГоловний принцип\n\nШукай не найгучніші новини, а найважливіші зміни.\n\nГоловне питання:\n«Що ця подія може змінити в майбутньому?»\n\nПеревагу надавай подіям, які можуть впливати на майбутнє людства, науку, штучний інтелект (ШІ), технології, космос, енергетику, клімат, демографію, суспільні відносини, відносини між чоловіками та жінками, економіку та геополітичний порядок.\n\nОсобливо звертай увагу на невеликі сьогодні події, які можуть стати великими тенденціями завтра.\n\nВійна\n\nРосійсько-українська війна — лише одна з тем.\n\nНе включай її до кожного огляду автоматично. Пиши про неї лише тоді, коли відбулися суттєві стратегічні зміни, які можуть вплинути на Україну, Європу, міжнародний порядок або майбутнє війни.\n\nНе дозволяй війні витісняти важливіші зміни у науці, технологіях, ШІ, космосі, суспільстві чи інших сферах.\n\nВідбір\n\nПроаналізуй приблизно останні 7 днів і вибери від 1 до 3 найважливіших тем.\n\nНе створюй додаткові теми штучно.\n\nОцінюй їх за:\n- впливом на майбутнє;\n- масштабом можливих змін;\n- довгостроковими наслідками;\n- значенням для людства;\n- значенням для України.\n\nДжерела\n\nПроводь достатній вебпошук.\n\nВикористовуй першоджерела, офіційні документи, наукові публікації, статистику, авторитетні українські та міжнародні медіа, а також дописи відомих людей у соціальних мережах (тільки якщо ці люди можуть бути першоджерелами цих новин або подій).\n\nВикористовуй і українські, і міжнародні джерела, оцінюючи їх за якістю, а не за країною походження.\n\nДля важливих або суперечливих тверджень використовуй декілька незалежних джерел.\n\nНе вигадуй фактів, статистики, цитат або джерел.\n\nАналіз\n\nДля кожної теми поясни:\nЩо сталося?\nЧому це сталося?\nЩо змінилося?\nЧому це важливо?\nХто отримує перевагу?\nЯкі можливі наслідки?\nЩо це означає для світу?\nЯкщо є прямий і суттєвий зв’язок з Україною — що це означає для України? Не шукай такого зв’язку штучно.\nЧи може це стати початком більшої тенденції?\n\nЧітко відокремлюй факти, власний аналіз та прогноз.\n\nПрогнози подавай як можливі сценарії, а не як встановлені факти.\n\nСтиль\n\nПиши українською.\n\nСтиль — живий, інтелектуальний, зрозумілий, аргументований і прямий.\n\nМова повинна бути живою та природною, без шаблонності.\nУ доречних місцях допускається гостра, різка й провокативна подача, якщо вона підсилює аргумент і випливає з аналізу.\nГострота не повинна перетворюватися на образи, дешеву сенсаційність або штучну драматизацію.\n\nНе використовуй зайвий пафос, канцелярит, журналістські кліше та повтори.\n\nНе створюй штучного «балансу думок», якщо факти дозволяють зробити однозначний висновок.\n\nНе перетворюй матеріал на стрічку новин.\n\nНе використовуй як заголовок або назву розділу формулювання «Аналіз Технократа» чи подібні саморекламні назви. Стаття сама є аналітичним матеріалом «Технократа».\n\nСтруктура\n\nМатеріал повинен містити:\nЗаголовок\nКороткий вступ\nГоловне за тиждень\nАналіз вибраних тем\nНе створюй постійного окремого розділу «Що це означає для України». Якщо подія справді має пряме значення для України, органічно поясни це у відповідному місці основного тексту. Не додавай український контекст до кожної теми лише заради структури.\nНе створюй постійного розділу з варіантами розвитку подій або сценаріями. Використовуй сценарний аналіз лише у виняткових випадках — коли тема справді дуже нова, надзвичайно важлива і невизначеність щодо її розвитку є центральною частиною аналізу.\nВисновок\nДжерела\n\nВикористовуй таблиці, графіки та інші візуальні матеріали лише тоді, коли вони реально допомагають зрозуміти тему.\n\nНе збільшуй матеріал штучно.\n\nКраще одна справді важлива тема з глибоким аналізом, ніж три поверхневі новини.\n\nФінальне правило\n\nНе пиши про те, що було важливим цього тижня. Пиши про те, що сталося цього тижня і може виявитися важливим для майбутнього.\n\nНе шукай новини про майбутнє. Шукай майбутнє в новинах.'

ARTICLE_LENGTH_RULE = f'''

Обсяг матеріалу

Текст для Telegram має бути стислим. Орієнтуйся на 20 000–22 000 знаків і в жодному разі не перевищуй {TARGET_ARTICLE_CHARS} знаків без нагальної потреби. Це приблизно 67% від технічної межі Rich Message Telegram і залишає запас для форматування та посилань. Не розтягуй статтю заради повноти: скорочуй повтори, другорядні деталі та поверхневі пояснення. Усі важливі джерела та їхні посилання обов'язково зберігай.
'''



def set_session(user_id: int, **values):
    session = USER_SESSIONS.setdefault(user_id, {})
    session.update(values)
    save_state()

def clear_session(user_id: int, *keys):
    session = USER_SESSIONS.get(user_id, {})
    for key in keys:
        session.pop(key, None)
    if not session:
        USER_SESSIONS.pop(user_id, None)
    save_state()

def get_session(user_id: int, key: str, default=None):
    return USER_SESSIONS.get(user_id, {}).get(key, default)


def authorized(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id == ADMIN_ID)


async def generate_review(editor_note: str = "") -> str:
    instruction = "Підготуй щотижневу статтю за останні 7 днів станом на зараз. Сьогодні субота. Особливо уважно відстежуй Україну, Росію, США, Європу, Китай, Близький Схід, технології, ШІ, науку, суспільні зміни та міжнародний порядок."
    if editor_note:
        instruction += f"\n\nРедакторська вказівка для доопрацювання: {editor_note}"
    response = await client.responses.create(
        model=MODEL,
        tools=[{"type": "web_search"}],
        input=SYSTEM_PROMPT + ARTICLE_LENGTH_RULE + "\n\n" + instruction,
    )
    return response.output_text.strip()


PENDING_DRAFT: dict[int, str] = {}
DRAFT_MESSAGE_IDS: dict[int, list[int]] = {}  # current preview messages per admin
# Channel post controls need only live callback state. The article itself is persisted
# in the channel message, while this mapping is recreated after each deployment.
CHANNEL_POST_STATES: dict[str, dict] = {}
FAVORITES: dict[int, list[dict[str, str]]] = {}
USER_SESSIONS: dict[int, dict] = {}

def load_state():
    global PENDING_DRAFT, FAVORITES, CHANNEL_POST_STATES, USER_SESSIONS
    try:
        raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        PENDING_DRAFT = {int(k): v for k, v in raw.get("pending_draft", {}).items()}
        FAVORITES = {int(k): v for k, v in raw.get("favorites", {}).items()}
        CHANNEL_POST_STATES = raw.get("channel_post_states", {})
        USER_SESSIONS = {int(k): v for k, v in raw.get("user_sessions", {}).items()}
    except (FileNotFoundError, json.JSONDecodeError, ValueError, TypeError):
        PENDING_DRAFT = {}
        FAVORITES = {}
        CHANNEL_POST_STATES = {}
        USER_SESSIONS = {}

def save_state():
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps({
        "pending_draft": {str(k): v for k, v in PENDING_DRAFT.items()},
        "favorites": {str(k): v for k, v in FAVORITES.items()},
        "channel_post_states": CHANNEL_POST_STATES,
        "user_sessions": {str(k): v for k, v in USER_SESSIONS.items()},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, STATE_FILE)

def add_favorite(user_id: int, text: str) -> int:
    items = FAVORITES.setdefault(user_id, [])
    # Avoid exact duplicates.
    for i, item in enumerate(items, 1):
        if item.get("text") == text:
            return i
    import datetime as _dt
    items.append({
        "text": text,
        "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat()
    })
    save_state()
    return len(items)

def remove_favorite(user_id: int, index: int):
    items = FAVORITES.get(user_id, [])
    if 1 <= index <= len(items):
        items.pop(index - 1)
        save_state()

load_state()



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
        input=SYSTEM_PROMPT + ARTICLE_LENGTH_RULE + "\n\n" + instruction,
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
        input=SYSTEM_PROMPT + ARTICLE_LENGTH_RULE + "\n\n" + prompt,
    )
    return response.output_text.strip()



def approval_keyboard(collapsed: bool = True, favorite: bool = False):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "🔽 Розгорнути" if collapsed else "🔼 Згорнути",
            callback_data="expand" if collapsed else "collapse"
        )],
        [InlineKeyboardButton(
            "⭐ Прибрати з обраного" if favorite else "⭐ Додати в обране",
            callback_data="unfavorite" if favorite else "favorite"
        )],
        [InlineKeyboardButton("✏️ Внести правки", callback_data="revise"),
         InlineKeyboardButton("📝 Ввести свій текст", callback_data="edit")],
        [InlineKeyboardButton("✅ Підтвердити і відправити", callback_data="approve")],
    ])

async def clear_draft_messages(bot, user_id: int):
    """Remove only the messages used by the current draft preview."""
    ids = DRAFT_MESSAGE_IDS.pop(user_id, [])
    if not ids:
        return
    token = bot.token
    url = f"https://api.telegram.org/bot{token}/deleteMessage"
    async with httpx.AsyncClient(timeout=30) as client_http:
        for mid in ids:
            try:
                r = await client_http.post(url, json={"chat_id": user_id, "message_id": mid})
                if r.status_code != 200:
                    logger.warning("Could not delete draft message %s: %s", mid, r.text)
            except Exception:
                logger.exception("Failed to delete draft message %s", mid)

async def show_draft(update_or_message, context, text: str, collapsed: bool = True, replace_previous: bool = True):
    user_id = update_or_message.from_user.id if hasattr(update_or_message, "from_user") and update_or_message.from_user else update_or_message.chat_id
    if replace_previous:
        await clear_draft_messages(context.bot, user_id)
    is_fav = any(item.get("text") == text for item in FAVORITES.get(user_id, []))
    markup = approval_keyboard(collapsed=collapsed, favorite=is_fav)
    ids = await send_long_message(context.bot, str(user_id), text, markup, collapse=collapsed)
    DRAFT_MESSAGE_IDS[user_id] = ids




def markdown_to_rich_html(text: str, collapse: bool = False) -> str:
    """Convert article Markdown/HTML into readable Telegram Rich Message HTML."""
    import re
    import html as _html

    # Protect administrator blocks and the publication disclaimer.
    admin_blocks = []
    def protect_admin(match):
        content = (match.group(1) if match.group(1) is not None else match.group(2)).strip()
        token = f"__ADMIN_BLOCK_{len(admin_blocks)}__"
        admin_blocks.append(content)
        return token

    text = re.sub(
        r"\[\[ADMIN\]\](.*?)\[\[/ADMIN\]\]|\[\[ADMIN:\s*(.*?)\]\]",
        protect_admin, text, flags=re.I | re.S
    )

    disclaimer_token = "[[AI_DISCLAIMER]]"
    has_disclaimer = disclaimer_token in text
    text = text.replace(disclaimer_token, "__AI_DISCLAIMER__")

    # Only treat input as already-HTML when it is genuinely HTML and does not
    # contain obvious Markdown syntax. This prevents one HTML fragment from
    # disabling conversion of the rest of a Markdown article.
    has_markdown = bool(re.search(
        r"(?m)^\s{0,3}#{1,6}\s+|\*\*[^*]+\*\*|\[([^\]]+)\]\(https?://|^\s*[-*+]\s+|^\s*\d+[.)]\s+",
        text
    ))
    looks_like_html = bool(re.match(r"^\s*<(?:html|article|h[1-6]|p|div|table|blockquote)\b", text, re.I))
    use_existing_html = looks_like_html and not has_markdown

    if use_existing_html:
        html_text = text
    else:
        lines = text.replace("\r\n", "\n").split("\n")
        out = []
        in_ul = in_ol = in_quote = False
        i = 0

        def inline(s: str) -> str:
            # Convert Markdown inline markup without allowing the automatic URL
            # pass to touch href attributes. The previous implementation first
            # created <a href="..."> and then ran the URL regex over that HTML,
            # which could corrupt links and make their visible text disappear in
            # Rich Messages (shown as empty parentheses in Telegram).
            placeholders = []

            def stash(value: str) -> str:
                token = f"@@INLINE_{len(placeholders)}@@"
                placeholders.append(value)
                return token

            # Markdown links: support URLs containing balanced parentheses too.
            link_re = re.compile(r"\[([^\]]+)\]\((https?://(?:[^\s()]+|\([^\s()]*\))+?)\)")
            def link_sub(m):
                label = _html.escape(m.group(1), quote=False)
                href = _html.escape(m.group(2), quote=True)
                return stash(f'<a href="{href}">{label}</a>')
            s = link_re.sub(link_sub, s)

            # Inline code is protected before applying emphasis.
            s = re.sub(r"`([^`]+)`", lambda m: stash(f'<code>{_html.escape(m.group(1), quote=False)}</code>'), s)

            s = _html.escape(s, quote=False)

            # Plain URLs are linked only in the remaining text, never inside the
            # already-protected Markdown links/code.
            s = re.sub(
                r'(?<!["=])(https?://[^\s<]+)',
                lambda m: stash(f'<a href="{_html.escape(m.group(1), quote=True)}">{_html.escape(m.group(1), quote=False)}</a>'),
                s
            )

            s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
            s = re.sub(r"__([^_]+)__", r"<b>\1</b>", s)
            s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", s)
            s = re.sub(r"(?<!_)_([^_]+)_(?!_)", r"<i>\1</i>", s)

            # Restore protected fragments after all text-level substitutions.
            for idx, value in enumerate(placeholders):
                s = s.replace(f"@@INLINE_{idx}@@", value)
            return s

        def close_lists():
            nonlocal in_ul, in_ol
            if in_ul:
                out.append("</ul>"); in_ul = False
            if in_ol:
                out.append("</ol>"); in_ol = False

        def close_quote():
            nonlocal in_quote
            if in_quote:
                out.append("</blockquote>"); in_quote = False

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if not stripped:
                close_lists(); close_quote()
                i += 1
                continue

            # Markdown table.
            if i + 1 < len(lines) and "|" in line and re.match(
                r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$",
                lines[i + 1]
            ):
                close_lists(); close_quote()
                def cells(x):
                    return [c.strip() for c in x.strip().strip("|").split("|")]
                headers = cells(line)
                out.append("<table><thead><tr>" +
                           "".join(f"<th>{inline(c)}</th>" for c in headers) +
                           "</tr></thead><tbody>")
                i += 2
                while i < len(lines) and "|" in lines[i] and lines[i].strip():
                    row = cells(lines[i])
                    out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>")
                    i += 1
                out.append("</tbody></table>")
                continue

            # Heading.
            m = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
            if m:
                close_lists(); close_quote()
                level = min(len(m.group(1)), 4)
                out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
                i += 1
                continue

            if re.match(r"^\s*(---+|___+|\*\s*\*\s*\*+)\s*$", line):
                close_lists(); close_quote()
                out.append("<hr/>")
                i += 1
                continue

            m = re.match(r"^\s*[-*+]\s+(.+)$", line)
            if m:
                close_quote()
                if not in_ul:
                    if in_ol: out.append("</ol>"); in_ol = False
                    out.append("<ul>"); in_ul = True
                out.append(f"<li>{inline(m.group(1))}</li>")
                i += 1
                continue

            m = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
            if m:
                close_quote()
                if not in_ol:
                    if in_ul: out.append("</ul>"); in_ul = False
                    out.append("<ol>"); in_ol = True
                out.append(f"<li>{inline(m.group(1))}</li>")
                i += 1
                continue

            m = re.match(r"^\s*>\s?(.*)$", line)
            if m:
                close_lists()
                if not in_quote:
                    out.append("<blockquote>"); in_quote = True
                out.append(inline(m.group(1)) + "<br/>")
                i += 1
                continue

            close_lists(); close_quote()
            out.append(f"<p>{inline(stripped)}</p>")
            i += 1

        close_lists(); close_quote()
        html_text = "".join(out)

    # Restore administrator text.
    for idx, content in enumerate(admin_blocks):
        safe = _html.escape(content, quote=False).replace("\n", "<br/>")
        rendered = (
            '<blockquote><b><i>Текст від Адміністратора каналу:</i></b><br/>'
            f'<i>{safe}</i></blockquote>'
        )
        html_text = html_text.replace(f"__ADMIN_BLOCK_{idx}__", rendered)

    # Restore the publication disclaimer directly as a normal paragraph.
    if has_disclaimer:
        disclaimer_html = (
            '<p><i>Стаття створена ШІ й акцептована відправка в групу Адміністратором.</i></p>'
        )
        html_text = html_text.replace("<p>__AI_DISCLAIMER__</p>", disclaimer_html)
        html_text = html_text.replace("__AI_DISCLAIMER__", disclaimer_html)

    if collapse:
        # Use Telegram's native <details> disclosure control only.
        # A <summary> inside it creates a second, non-functional "Показати більше"
        # row on some Android clients, while the native blue control is the real
        # disclosure button. Therefore the details block intentionally has no
        # explicit <summary>.
        parts = re.findall(
            r"<h[1-6][^>]*>.*?</h[1-6]>|<p[^>]*>.*?</p>|<ul>.*?</ul>|<ol>.*?</ol>|<table>.*?</table>|<hr/>",
            html_text, re.I | re.S
        )
        if len(parts) > 3:
            title_idx = next((i for i,p in enumerate(parts) if re.match(r"<h[1-6]", p, re.I)), None)
            disclaimer_idx = next((i for i,p in enumerate(parts) if "Стаття створена ШІ" in p), None)

            keep = []
            if title_idx is not None: keep.append(title_idx)
            if disclaimer_idx is not None: keep.append(disclaimer_idx)

            # Show a short lead/annotation in the collapsed preview.
            lead_idx = None
            lead_preview = ""
            for i,p in enumerate(parts):
                if re.match(r"<p\b", p, re.I) and "Стаття створена ШІ" not in p:
                    plain = re.sub(r"<[^>]+>", " ", p)
                    plain = re.sub(r"\s+", " ", plain).strip()
                    if len(plain) >= 40:
                        lead_idx = i
                        if len(plain) > 360:
                            sentences = re.split(r"(?<=[.!?])\s+", plain)
                            chosen = ""
                            for s in sentences:
                                candidate = (chosen + " " + s).strip()
                                if len(candidate) <= 360:
                                    chosen = candidate
                                else:
                                    break
                            if len(chosen) < 100:
                                chosen = plain[:357].rstrip() + "…"
                            elif not chosen.endswith((".", "!", "?", "…")):
                                chosen += "…"
                            lead_preview = f"<p>{_html.escape(chosen, quote=False)}</p>"
                        else:
                            lead_preview = p
                        keep.append(i)
                        break

            keep=set(keep)
            visible_parts=[]
            rest_parts=[]
            for i,p in enumerate(parts):
                if i in keep:
                    visible_parts.append(lead_preview if i == lead_idx else p)
                    # If the lead was truncated, keep the full original paragraph
                    # inside the expandable part so no information is lost.
                    if i == lead_idx and lead_preview != p:
                        rest_parts.append(p)
                else:
                    rest_parts.append(p)

            visible="".join(visible_parts)
            rest="".join(rest_parts)
            if rest.strip():
                # Use an explicit Telegram Rich Message summary so the disclosure
                # control has a real target instead of relying on the client
                # fallback summary.
                return visible + f"<details><summary>Показати більше</summary>{rest}</details>"

    return html_text





class _RichHTMLParser(__import__("html.parser", fromlist=["HTMLParser"]).HTMLParser):
    """Small HTML -> Telegram InputRichBlock converter for native rich blocks."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root=[]
        self.stack=[]

    def _container(self):
        return self.stack[-1]["children"] if self.stack else self.root

    def handle_starttag(self, tag, attrs):
        tag=tag.lower()
        if tag in {"p","h1","h2","h3","h4","h5","h6","blockquote","ul","ol","li","pre","code","b","strong","i","em","u","s","del","a","details","summary"}:
            node={"tag":tag,"attrs":dict(attrs),"children":[] ,"text":""}
            self._container().append(node)
            self.stack.append(node)
        elif tag=="br":
            self._container().append({"tag":"#text","text":"\n","children":[]})
        elif tag=="hr":
            self._container().append({"tag":"hr","children":[]})

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.lower() not in {"br","hr"}:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag=tag.lower()
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i]["tag"]==tag:
                self.stack=self.stack[:i]
                return

    def handle_data(self, data):
        if data:
            self._container().append({"tag":"#text","text":data,"children":[]})

def _rich_inline(nodes):
    out=[]
    for n in nodes:
        tag=n["tag"]
        if tag=="#text":
            out.append(n["text"]); continue
        inner=_rich_inline(n.get("children",[]))
        if tag in {"b","strong"}: out.append({"type":"bold","text":inner})
        elif tag in {"i","em"}: out.append({"type":"italic","text":inner})
        elif tag=="u": out.append({"type":"underline","text":inner})
        elif tag in {"s","del"}: out.append({"type":"strikethrough","text":inner})
        elif tag=="code": out.append({"type":"code","text":inner})
        elif tag=="a": out.append({"type":"url","text":inner,"url":n.get("attrs",{}).get("href","")})
        elif tag=="br": out.append("\n")
        else: out.append(inner)
    return out if len(out)>1 else (out[0] if out else "")

def _rich_blocks(nodes):
    blocks=[]
    for n in nodes:
        tag=n["tag"]
        if tag=="#text":
            txt=n["text"].strip()
            if txt: blocks.append({"type":"paragraph","text":txt})
        elif tag in {"p","footer"}:
            txt=_rich_inline(n.get("children",[]))
            if txt: blocks.append({"type":"paragraph" if tag=="p" else "footer","text":txt})
        elif tag in {"h1","h2","h3","h4","h5","h6"}:
            txt=_rich_inline(n.get("children",[]))
            if txt: blocks.append({"type":"heading","text":txt,"size":min(int(tag[1]),6)})
        elif tag=="hr": blocks.append({"type":"divider"})
        elif tag=="blockquote":
            inner=_rich_blocks(n.get("children",[]))
            if inner: blocks.append({"type":"blockquote","blocks":inner})
        elif tag in {"ul","ol"}:
            items=[]
            for li in n.get("children",[]):
                if li.get("tag")!="li": continue
                ib=_rich_blocks(li.get("children",[]))
                if ib: items.append({"blocks":ib})
            if items: blocks.append({"type":"list","items":items})
        elif tag=="pre":
            txt=_rich_inline(n.get("children",[]))
            if txt: blocks.append({"type":"pre","text":txt})
        elif tag=="details":
            summary="Показати більше"
            body=[]
            for c in n.get("children",[]):
                if c.get("tag")=="summary": summary=_rich_inline(c.get("children",[]))
                else: body.extend(_rich_blocks([c]))
            if body: blocks.append({"type":"details","summary":summary,"blocks":body})
        elif tag=="summary":
            continue
    return blocks

def html_to_rich_blocks(html_text: str):
    parser=_RichHTMLParser(); parser.feed(html_text); parser.close()
    return _rich_blocks(parser.root)


def _source_links(text: str):
    """Return source URLs with labels, preserving every link from the approved draft."""
    entries = []
    seen = set()
    # Markdown links first, so we can preserve their human-readable labels.
    md_re = re.compile(r"\[([^\]]+)\]\((https?://(?:[^\s()]+|\([^\s()]*\))+?)\)")
    for m in md_re.finditer(text):
        label, url = m.group(1).strip(), m.group(2).strip()
        if url not in seen:
            entries.append((label or url, url)); seen.add(url)
    # Also preserve bare URLs. Strip punctuation that commonly follows a URL in prose.
    for m in re.finditer(r"https?://[^\s<>]+", text):
        url = m.group(0).rstrip('.,;:!?)]}\"\'')
        if url and url not in seen:
            entries.append((url, url)); seen.add(url)
    return entries


def _urls_in_rich(value):
    """Collect URL targets recursively from Telegram Rich Message blocks."""
    found = set()
    if isinstance(value, dict):
        if value.get("type") == "url" and value.get("url"):
            found.add(value["url"])
        for v in value.values():
            found.update(_urls_in_rich(v))
    elif isinstance(value, list):
        for v in value:
            found.update(_urls_in_rich(v))
    return found


def ensure_all_source_links(full_blocks, original_text: str):
    """Guarantee that publication keeps every URL present in the approved draft.

    Markdown -> HTML -> Rich Blocks conversion can occasionally drop an unusual URL.
    Any missing target is therefore restored as a clickable source paragraph before
    the channel message is stored/published.
    """
    entries = _source_links(original_text)
    present = _urls_in_rich(full_blocks)
    missing = [(label, url) for label, url in entries if url not in present]
    if not missing:
        return full_blocks
    full_blocks.append({"type": "heading", "text": "Джерела — додаткові посилання", "size": 3})
    for label, url in missing:
        full_blocks.append({
            "type": "paragraph",
            "text": {"type": "url", "text": label, "url": url},
        })
    logger.warning("Restored %d source link(s) lost during Rich Message conversion", len(missing))
    return full_blocks



async def send_rich_message(bot, chat_id: str | int, html_text: str, reply_markup=None, collapse: bool = False, native_blocks: bool = False):
    """Send Telegram Rich Message and return its message id when available."""
    html_text = markdown_to_rich_html(html_text, collapse=False)
    token = bot.token
    url = f"https://api.telegram.org/bot{token}/sendRichMessage"
    if native_blocks:
        blocks = html_to_rich_blocks(html_text)
        payload = {"chat_id": chat_id, "rich_message": {"blocks": blocks}, "disable_notification": False}
    else:
        if collapse:
            html_text = markdown_to_rich_html(html_text, collapse=True)
        payload = {"chat_id": chat_id, "rich_message": {"html": html_text}, "disable_notification": False}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup.to_dict()
    async with httpx.AsyncClient(timeout=90) as client_http:
        response = await client_http.post(url, json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"Telegram sendRichMessage failed: {response.text}")
        try:
            result = response.json().get("result")
            if isinstance(result, dict):
                return result.get("message_id")
        except Exception:
            pass
        return None




async def send_plain_fallback(bot, chat_id: str | int, text: str, reply_markup=None):
    """Fallback for malformed rich HTML or unavailable Rich Message endpoint."""
    clean = text.replace("<hr/>", "\n──────────\n")
    import re
    clean = re.sub(r"<[^>]+>", "", clean)
    msg = await bot.send_message(
        chat_id=chat_id, text=clean[:4096],
        disable_web_page_preview=True, reply_markup=reply_markup,
    )
    return getattr(msg, "message_id", None)



async def send_long_message(bot, chat_id: str | int, text: str, reply_markup=None, collapse: bool = False):
    """Send text and return IDs of all messages belonging to this preview."""
    sent_ids = []
    if len(text) <= MAX_ARTICLE_CHARS:
        try:
            mid = await send_rich_message(bot, chat_id, text, reply_markup, collapse=collapse)
        except Exception:
            logger.exception("Rich message failed; using plain fallback")
            mid = await send_plain_fallback(bot, chat_id, text, reply_markup)
        if mid:
            sent_ids.append(mid)
        return sent_ids

    chunks, remaining = [], text
    while len(remaining) > MAX_ARTICLE_CHARS:
        cut = remaining.rfind("</p>", 0, MAX_ARTICLE_CHARS)
        if cut < 1000: cut = remaining.rfind("</div>", 0, MAX_ARTICLE_CHARS)
        if cut < 1000: cut = remaining.rfind("\n", 0, MAX_ARTICLE_CHARS)
        if cut < 1000: cut = MAX_ARTICLE_CHARS
        cut = cut + 4 if remaining[cut:cut+4] == "</p>" else cut
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip()
    if remaining: chunks.append(remaining)

    for i, chunk in enumerate(chunks):
        markup = reply_markup if i == len(chunks)-1 else None
        try:
            mid = await send_rich_message(bot, chat_id, chunk, markup, collapse=collapse if i == 0 else False)
        except Exception:
            logger.exception("Rich chunk failed; using plain fallback")
            mid = await send_plain_fallback(bot, chat_id, chunk, markup)
        if mid:
            sent_ids.append(mid)
    return sent_ids




async def keep_article_within_budget(text: str) -> str:
    """Condense generated/editorial text when it exceeds the publishing budget.

    This is deliberately done before Rich Message conversion so source links are
    preserved as Markdown links instead of being lost while splitting/truncating
    the rendered message.
    """
    # Enforce the editorial target, not merely Telegram's technical ceiling.
    # This guarantees that weekly drafts fit comfortably into ONE Rich Message.
    if len(text) <= TARGET_ARTICLE_CHARS:
        return text

    prompt = f"""Скороти цей матеріал для публікації в Telegram.

Жорстка вимога: результат має бути не довшим за {TARGET_ARTICLE_CHARS} знаків.
Збережи головну думку, ключові факти, висновки та структуру.
Прибери повтори, другорядні подробиці, зайві вступи та словесний шум.

КРИТИЧНО ВАЖЛИВО:
- збережи ВСІ важливі джерела з кінцевого розділу «Джерела»;
- не видаляй і не змінюй URL у Markdown-посиланнях виду [назва](https://...);
- не замінюй посилання порожніми дужками;
- не вигадуй нових джерел;
- поверни повний готовий текст статті, без пояснення того, що ти скоротила.

Текст:
{text}
"""
    try:
        response = await client.responses.create(
            model=MODEL,
            tools=[],
            input=prompt,
        )
        shortened = response.output_text.strip()
        if shortened and len(shortened) <= TARGET_ARTICLE_CHARS:
            return shortened
        # If the model still exceeds the editorial target, keep the source section
        # and trim the body at a paragraph boundary rather than splitting the draft.
        return safe_trim_article(shortened or text, TARGET_ARTICLE_CHARS)
    except Exception:
        logger.exception("Article condensation failed; applying safe local trim")
        return safe_trim_article(text, TARGET_ARTICLE_CHARS)


def safe_trim_article(text: str, limit: int = MAX_ARTICLE_CHARS) -> str:
    """Trim at paragraph boundaries while preserving the Sources section."""
    if len(text) <= limit:
        return text
    import re
    m = re.search(r'(?im)^#{1,6}\s*Джерела\s*$', text)
    sources = text[m.start():] if m else ""
    body = text[:m.start()] if m else text
    if sources and len(sources) < limit:
        budget = limit - len(sources) - 2
        cut = body[:budget]
        # Do not cut in the middle of a Markdown link.
        cut = cut.rsplit("\n\n", 1)[0]
        if not cut:
            cut = body[:budget].rsplit("\n", 1)[0]
        return cut.rstrip() + "\n\n" + sources.lstrip()
    # Last-resort paragraph boundary.
    cut = text[:limit]
    return cut.rsplit("\n\n", 1)[0].rstrip()


async def deliver_to_group(bot, text: str):
    """Publish an approved article with exactly one custom Rich Message button.

    We deliberately do not use Telegram's native <details> block here. In the
    Android client it can coexist with the client's own long-message "Show more"
    control, producing two different expand affordances. Instead, the post is
    sent in a compact state with one primary Rich Message button; pressing it
    edits the same channel message to the full article, and the same button then
    becomes "Згорнути".
    """
    import re
    import secrets

    # Keep every published Rich Message comfortably below Telegram's 32,768-char
    # limit. This also prevents the final source links from being pushed out by
    # formatting overhead.
    text = await keep_article_within_budget(text)

    disclaimer_token = "[[AI_DISCLAIMER]]"
    if text and disclaimer_token not in text:
        md = re.search(r"(?m)^\s*#{1,6}\s+.+?\s*#*\s*$", text)
        if md:
            insert_at = md.end()
            text = text[:insert_at] + "\n\n" + disclaimer_token + "\n" + text[insert_at:]
        else:
            text = disclaimer_token + "\n" + text

    html_text = markdown_to_rich_html(text, collapse=False)
    full_blocks = html_to_rich_blocks(html_text)
    # Validate link integrity after Markdown/HTML conversion. Telegram publication
    # must contain every URL that was present in the approved draft.
    full_blocks = ensure_all_source_links(full_blocks, text)

    # Make sure the first line is rendered as a real heading even if a manually
    # entered article omitted Markdown's # before the title.
    if full_blocks and full_blocks[0].get("type") == "paragraph":
        first_text = full_blocks[0].get("text", "")
        if isinstance(first_text, str) and first_text.strip():
            full_blocks[0] = {"type": "heading", "text": first_text.strip(), "size": 2}

    # Compact preview: title + publication notice + first meaningful paragraph.
    title_idx = next((i for i, b in enumerate(full_blocks) if b.get("type") == "heading"), None)
    notice_idx = next((i for i, b in enumerate(full_blocks)
                       if "Стаття створена ШІ" in str(b.get("text", ""))), None)
    lead_idx = next((i for i, b in enumerate(full_blocks)
                     if b.get("type") == "paragraph" and i != notice_idx), None)

    compact = []
    for idx in (title_idx, notice_idx, lead_idx):
        if idx is not None and full_blocks[idx] not in compact:
            compact.append(full_blocks[idx])

    if not compact:
        compact = full_blocks[:2]

    key = secrets.token_hex(6)
    CHANNEL_POST_STATES[key] = {
        "full_blocks": full_blocks,
        "compact_blocks": compact,
        "chat_id": CHANNEL_ID,
    }

    def button(label: str, action: str):
        return {
            "type": "buttons",
            "align": "center",
            "buttons": [{
                "text": label,
                "style": "primary",
                "callback_data": f"channel:{action}:{key}",
            }],
        }

    payload = {
        "chat_id": CHANNEL_ID,
        "rich_message": {
            "blocks": compact + [button("Розгорнути", "expand")]
        },
        "disable_notification": False,
    }
    token = bot.token
    url = f"https://api.telegram.org/bot{token}/sendRichMessage"
    async with httpx.AsyncClient(timeout=90) as client_http:
        response = await client_http.post(url, json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"Telegram sendRichMessage failed: {response.text}")
        data = response.json()
        result = data.get("result") or {}
        if isinstance(result, dict) and result.get("message_id"):
            CHANNEL_POST_STATES[key]["message_id"] = result["message_id"]
        # Keep only recent channel controls so the state file stays small.
        if len(CHANNEL_POST_STATES) > 30:
            oldest = list(CHANNEL_POST_STATES.keys())[:-30]
            for old_key in oldest:
                CHANNEL_POST_STATES.pop(old_key, None)
        save_state()


async def create_and_send_for_approval(bot, chat_id: int):
    await bot.send_message(chat_id=chat_id, text="Готую щотижневу статтю. Це може зайняти кілька хвилин…")
    try:
        post = await generate_review()
        # The weekly draft must always fit in one Telegram Rich Message.
        post = await keep_article_within_budget(post)
        PENDING_DRAFT[chat_id] = post
        save_state()
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
    if not get_session(update.effective_user.id, "manual_edit", False):
        await update.message.reply_text("Зараз немає режиму ручного введення статті.")
        return
    parts = get_session(update.effective_user.id, "manual_parts", [])
    if not parts:
        await update.message.reply_text("Ви ще не надіслали текст.")
        return

    draft = "\n\n".join(parts).strip()
    user_id = update.effective_user.id
    PENDING_DRAFT[user_id] = draft
    save_state()
    clear_session(user_id, "manual_edit", "manual_parts")

    await update.message.reply_text("Готово. Ваш текст встановлено як нову чернетку. Перевірте його:")
    await show_draft(update, context, draft, collapsed=True)



async def favorites_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    items = FAVORITES.get(update.effective_user.id, [])
    if not items:
        await update.message.reply_text("⭐ «Обране» поки порожнє.")
        return
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    rows = []
    for idx, item in enumerate(items, 1):
        title = re.sub(r"<[^>]+>", "", item.get("text", "")).strip().split("\n")[0]
        title = title[:55] if title else f"Матеріал {idx}"
        rows.append([InlineKeyboardButton(f"⭐ {idx}. {title}", callback_data=f"favview:{idx}")])
    await update.message.reply_text(
        "⭐ Ваше «Обране»:",
        reply_markup=InlineKeyboardMarkup(rows)
    )


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    if update.effective_user.id not in PENDING_DRAFT:
        await update.message.reply_text("Спочатку створіть або відкрийте чернетку.")
        return
    set_session(update.effective_user.id, admin_insert_mode=True)
    await update.message.reply_text(
        "Надішліть текст вашої думки. Я збережу його як текст Адміністратора. "
        "Щоб вставити його в потрібне місце, найнадійніше використовувати [[ADMIN]]...[[/ADMIN]] "
        "у ручному тексті. Для швидкої вставки я додам його наприкінці поточної чернетки."
    )


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    user_id = update.effective_user.id
    existed = PENDING_DRAFT.pop(user_id, None) is not None
    save_state()
    clear_session(user_id, "revision_edit")
    clear_session(user_id, "manual_edit", "manual_parts")
    clear_session(user_id, "awaiting_question")
    if existed:
        await update.message.reply_text("Поточну чернетку скасовано. Її не буде опубліковано.")
    else:
        await update.message.reply_text("Активної чернетки немає.")


async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return

    question = " ".join(context.args).strip()
    if not question:
        set_session(update.effective_user.id, awaiting_question=True)
        await update.message.reply_text(
            "Напишіть питання одним повідомленням. Я проведу вебпошук і зроблю окремий аналіз."
        )
        return

    await update.message.reply_text("Шукаю інформацію та готую відповідь…")
    try:
        answer = await generate_answer(question)
        PENDING_DRAFT[update.effective_user.id] = answer
        await show_draft(update, context, answer, collapsed=True)
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
        "/done — завершити ручне введення статті\n/cancel — скасувати поточну чернетку\n/favorites — моє «Обране»\n/admin — додати власну думку до поточної чернетки\n"
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

    # Public channel post controls. These must be handled before the admin-only
    # draft controls because any subscriber may press the channel button.
    if query.data and query.data.startswith("channel:"):
        try:
            _, action, key = query.data.split(":", 2)
            state = CHANNEL_POST_STATES.get(key)
            if not state or not query.message:
                return
            blocks = state["full_blocks"] if action == "expand" else state["compact_blocks"]
            label = "Згорнути" if action == "expand" else "Розгорнути"
            blocks = blocks + [{
                "type": "buttons",
                "align": "center",
                "buttons": [{
                    "text": label,
                    "style": "primary",
                    "callback_data": f"channel:{'collapse' if action == 'expand' else 'expand'}:{key}",
                }],
            }]
            token = context.bot.token
            url = f"https://api.telegram.org/bot{token}/editMessageText"
            payload = {
                "chat_id": query.message.chat.id,
                "message_id": query.message.message_id,
                "rich_message": {"blocks": blocks},
            }
            async with httpx.AsyncClient(timeout=90) as client_http:
                response = await client_http.post(url, json=payload)
                if response.status_code != 200:
                    logger.warning("Channel post edit failed: %s", response.text)
        except Exception:
            logger.exception("Channel expand/collapse failed")
        return

    if not query.from_user or query.from_user.id != ADMIN_ID:
        return
    user_id = query.from_user.id
    draft = PENDING_DRAFT.get(user_id)
    if not draft:
        await query.message.reply_text("Чернетка вже відсутня або була оброблена. Створіть нову через /preview або /ask.")
        return

    if query.data in ("expand", "collapse"):
        collapsed = query.data == "collapse"
        await show_draft(query, context, draft, collapsed=collapsed)
        return

    if query.data == "favorite":
        add_favorite(user_id, draft)
        await query.message.reply_text("⭐ Матеріал додано до «Обраного». Для перегляду використовуйте /favorites.")
        await show_draft(query, context, draft, collapsed=True)
        return

    if query.data == "unfavorite":
        items = FAVORITES.get(user_id, [])
        for idx, item in enumerate(items, 1):
            if item.get("text") == draft:
                remove_favorite(user_id, idx)
                break
        await query.message.reply_text("Матеріал прибрано з «Обраного».")
        await show_draft(query, context, draft, collapsed=True)
        return

    if query.data.startswith("favview:"):
        try:
            idx = int(query.data.split(":", 1)[1])
            items = FAVORITES.get(user_id, [])
            if not (1 <= idx <= len(items)):
                await query.message.reply_text("Цей матеріал більше не знайдено в «Обраному».")
                return
            fav_text = items[idx - 1].get("text", "")
            PENDING_DRAFT[user_id] = fav_text
            save_state()
            await show_draft(query, context, fav_text, collapsed=True)
        except (ValueError, IndexError):
            await query.message.reply_text("Не вдалося відкрити цей матеріал.")
        return

    if query.data == "approve":
        try:
            await deliver_to_group(context.bot, draft)
            await clear_draft_messages(context.bot, user_id)
            PENDING_DRAFT.pop(user_id, None)
            save_state()
            clear_session(user_id, "revision_edit")
            clear_session(user_id, "manual_edit")
            clear_session(user_id, "manual_parts")
            await query.message.reply_text("Готово. Матеріал підтверджено та відправлено в групу.")
        except Exception as exc:
            logger.exception("Publication failed")
            await query.message.reply_text(f"Не вдалося опублікувати: {type(exc).__name__}: {exc}")
        return

    if query.data == "revise":
        set_session(update.effective_user.id, revision_edit=True)
        clear_session(user_id, "manual_edit")
        clear_session(user_id, "manual_parts")
        await query.message.reply_text(
            "Напишіть одним повідомленням, що саме потрібно змінити. Я перероблю поточну версію. Власну думку, яку треба дослівно вставити, можна позначити [[ADMIN]]...[[/ADMIN]]."
        )
        return

    if query.data == "edit":
        set_session(update.effective_user.id, manual_edit=True)
        set_session(update.effective_user.id, manual_parts=[])
        clear_session(user_id, "revision_edit")
        await query.message.reply_text(
            "Надішліть свій готовий текст замість цієї чернетки. "
            "Можна одним повідомленням або кількома частинами. Після останньої частини надішліть /done."
        )






async def text_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return

    user_id = update.effective_user.id

    if get_session(update.effective_user.id, "admin_insert_mode", False):
        admin_text = update.message.text.strip()
        if not admin_text:
            return
        draft = PENDING_DRAFT.get(user_id)
        if not draft:
            clear_session(user_id, "admin_insert_mode")
            await update.message.reply_text("Поточна чернетка вже відсутня.")
            return
        clear_session(user_id, "admin_insert_mode")
        PENDING_DRAFT[user_id] = draft + "\n\n[[ADMIN]]" + admin_text + "[[/ADMIN]]"
        save_state()
        await update.message.reply_text(
            "Думку додано до чернетки. Для вставлення її в інше місце скористайтеся «Ввести свій текст» "
            "і маркерами [[ADMIN]]...[[/ADMIN]]."
        )
        await show_draft(update, context, PENDING_DRAFT[user_id], collapsed=True)
        return

    if get_session(update.effective_user.id, "awaiting_question", False):
        question = update.message.text.strip()
        clear_session(user_id, "awaiting_question")
        await update.message.reply_text("Шукаю інформацію та готую відповідь…")
        try:
            answer = await generate_answer(question)
            PENDING_DRAFT[user_id] = answer
            save_state()
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

    if get_session(update.effective_user.id, "revision_edit", False):
        instruction = update.message.text.strip()
        if not instruction:
            return
        draft = PENDING_DRAFT.get(user_id)
        if not draft:
            clear_session(user_id, "revision_edit")
            await update.message.reply_text("Поточна чернетка вже відсутня. Створіть новий аналіз через /ask.")
            return

        clear_session(user_id, "revision_edit")
        await update.message.reply_text("Вношу правки та перевіряю фактичні зміни…")
        try:
            revised = await revise_draft(draft, instruction)
            PENDING_DRAFT[user_id] = revised
            save_state()
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

    if not get_session(update.effective_user.id, "manual_edit", False):
        return

    part = update.message.text
    if not part.strip():
        return
    get_session(user_id, "manual_parts", []).append(part)
    save_state()
    count = len(get_session(update.effective_user.id, "manual_parts", []))
    await update.message.reply_text(
        f"Отримала частину {count}. Надішліть наступну частину або /done, якщо це був останній фрагмент."
    )





async def process_update_background(update: Update):
    try:
        await application.process_update(update)
    except Exception:
        logger.exception("Update processing failed")


async def generate_weekly_background():
    try:
        await create_and_send_for_approval(application.bot, ADMIN_ID)
        logger.info("Weekly draft generated for approval")
    except Exception:
        logger.exception("Weekly draft generation failed")


application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_cmd))
application.add_handler(CommandHandler("post", make_post))
application.add_handler(CommandHandler("preview", preview))
application.add_handler(CommandHandler("ask", ask_cmd))
application.add_handler(CommandHandler("cancel", cancel_cmd))
application.add_handler(CommandHandler("favorites", favorites_cmd))
application.add_handler(CommandHandler("admin", admin_cmd))
application.add_handler(CommandHandler("done", done_edit))
application.add_handler(CallbackQueryHandler(callbacks))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_edit))

web = FastAPI(title="Tehnokratu Bot")

@web.get("/")
async def root():
    return {"status": "ok", "service": "tehnokratu-bot"}

@web.get("/health")
async def health():
    return {"status": "ok"}

@web.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    payload = await request.json()
    update = Update.de_json(payload, application.bot)
    asyncio.create_task(process_update_background(update))
    return JSONResponse({"ok": True})

@web.post("/internal/weekly")
async def internal_weekly(x_schedule_secret: str | None = Header(default=None)):
    if not SCHEDULE_SECRET or x_schedule_secret != SCHEDULE_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    asyncio.create_task(generate_weekly_background())
    return JSONResponse({"ok": True, "started": True}, status_code=202)

@web.on_event("startup")
async def startup():
    await application.initialize()
    await application.start()
    public_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    if public_domain:
        webhook_url = f"https://{public_domain}{WEBHOOK_PATH}"
        await application.bot.set_webhook(url=webhook_url, allowed_updates=Update.ALL_TYPES)
        logger.info("Telegram webhook set to %s", webhook_url)
    else:
        logger.warning("RAILWAY_PUBLIC_DOMAIN is not set; Telegram webhook was not configured")

@web.on_event("shutdown")
async def shutdown():
    try:
        await application.bot.delete_webhook(drop_pending_updates=False)
    except Exception:
        logger.exception("Could not delete Telegram webhook")
    await application.stop()
    await application.shutdown()


def main():
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(web, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
