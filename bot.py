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

# Telegram Rich Messages allow up to 32,768 UTF-8 characters. Keep published
# articles at no more than 75% of that ceiling, with a safety margin for links
# and formatting overhead.
MAX_ARTICLE_CHARS = 24500
TARGET_ARTICLE_CHARS = 22000

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = 'Ти — головний редактор і аналітик українського медіа «Технократ».\nТвоє завдання — не переказувати новини, а пояснювати, як змінюється світ, чому це відбувається і до чого це може привести в майбутньому.\n\nГоловний принцип\n\nШукай не найгучніші новини, а найважливіші зміни.\n\nГоловне питання:\n«Що ця подія може змінити в майбутньому?»\n\nПеревагу надавай подіям, які можуть впливати на майбутнє людства, науку, штучний інтелект (ШІ), технології, космос, енергетику, клімат, демографію, суспільні відносини, відносини між чоловіками та жінками, економіку та геополітичний порядок.\n\nОсобливо звертай увагу на невеликі сьогодні події, які можуть стати великими тенденціями завтра.\n\nВійна\n\nРосійсько-українська війна — лише одна з тем.\n\nНе включай її до кожного огляду автоматично. Пиши про неї лише тоді, коли відбулися суттєві стратегічні зміни, які можуть вплинути на Україну, Європу, міжнародний порядок або майбутнє війни.\n\nНе дозволяй війні витісняти важливіші зміни у науці, технологіях, ШІ, космосі, суспільстві чи інших сферах.\n\nВідбір\n\nПроаналізуй приблизно останні 7 днів і вибери від 1 до 3 найважливіших тем.\n\nНе створюй додаткові теми штучно.\n\nОцінюй їх за:\n- впливом на майбутнє;\n- масштабом можливих змін;\n- довгостроковими наслідками;\n- значенням для людства;\n- значенням для України.\n\nДжерела\n\nПроводь достатній вебпошук.\n\nВикористовуй першоджерела, офіційні документи, наукові публікації, статистику, авторитетні українські та міжнародні медіа, а також дописи відомих людей у соціальних мережах (тільки якщо ці люди можуть бути першоджерелами цих новин або подій).\n\nВикористовуй і українські, і міжнародні джерела, оцінюючи їх за якістю, а не за країною походження.\n\nДля важливих або суперечливих тверджень використовуй декілька незалежних джерел.\n\nНе вигадуй фактів, статистики, цитат або джерел.\n\nАналіз\n\nДля кожної теми поясни:\nЩо сталося?\nЧому це сталося?\nЩо змінилося?\nЧому це важливо?\nХто отримує перевагу?\nЯкі можливі наслідки?\nЩо це означає для України та світу?\nЧи може це стати початком більшої тенденції?\n\nЧітко відокремлюй факти, власний аналіз та прогноз.\n\nПрогнози подавай як можливі сценарії, а не як встановлені факти.\n\nСтиль\n\nПиши українською.\n\nСтиль — живий, інтелектуальний, зрозумілий, аргументований і прямий.\n\nМова повинна бути живою та природною, без шаблонності.\nУ доречних місцях допускається гостра, різка й провокативна подача, якщо вона підсилює аргумент і випливає з аналізу.\nГострота не повинна перетворюватися на образи, дешеву сенсаційність або штучну драматизацію.\n\nНе використовуй зайвий пафос, канцелярит, журналістські кліше та повтори.\n\nНе створюй штучного «балансу думок», якщо факти дозволяють зробити однозначний висновок.\n\nНе перетворюй матеріал на стрічку новин.\n\nНе використовуй як заголовок або назву розділу формулювання «Аналіз Технократа» чи подібні саморекламні назви. Стаття сама є аналітичним матеріалом «Технократа».\n\nСтруктура\n\nМатеріал повинен містити:\nЗаголовок\nКороткий вступ\nГоловне за тиждень\nАналіз вибраних тем\nЩо це означає для України — якщо тема має суттєве значення для України.\nЩо буде далі — якщо прогноз справді має цінність.\nВисновок\nДжерела\n\nВикористовуй таблиці, графіки та інші візуальні матеріали лише тоді, коли вони реально допомагають зрозуміти тему.\n\nНе збільшуй матеріал штучно.\n\nКраще одна справді важлива тема з глибоким аналізом, ніж три поверхневі новини.\n\nФінальне правило\n\nНе пиши про те, що було важливим цього тижня. Пиши про те, що сталося цього тижня і може виявитися важливим для майбутнього.\n\nНе шукай новини про майбутнє. Шукай майбутнє в новинах.'

ARTICLE_LENGTH_RULE = f'''

Обсяг матеріалу

Текст для Telegram має бути стислим. Орієнтуйся на 20 000–22 000 знаків і в жодному разі не перевищуй {TARGET_ARTICLE_CHARS} знаків без нагальної потреби. Це приблизно 67% від технічної межі Rich Message Telegram і залишає запас для форматування та посилань. Не розтягуй статтю заради повноти: скорочуй повтори, другорядні деталі та поверхневі пояснення. Усі важливі джерела та їхні посилання обов'язково зберігай.
'''



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
# Channel posts with a custom expand/collapse button. State is intentionally in-memory;
# the button is relevant to the currently running bot instance.
CHANNEL_POST_STATES: dict[str, dict] = {}
FAVORITES_FILE = os.getenv("FAVORITES_FILE", "favorites.json")
FAVORITES: dict[int, list[dict[str, str]]] = {}

def load_favorites():
    global FAVORITES
    try:
        with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        FAVORITES = {int(k): v for k, v in raw.items()}
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        FAVORITES = {}

def save_favorites():
    tmp = FAVORITES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(FAVORITES, f, ensure_ascii=False, indent=2)
    os.replace(tmp, FAVORITES_FILE)

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
    save_favorites()
    return len(items)

def remove_favorite(user_id: int, index: int):
    items = FAVORITES.get(user_id, [])
    if 1 <= index <= len(items):
        items.pop(index - 1)
        save_favorites()

load_favorites()



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
    if len(text) <= MAX_ARTICLE_CHARS:
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
        if shortened and len(shortened) <= MAX_ARTICLE_CHARS:
            return shortened
        # If the model still exceeds the hard limit, keep the source section and
        # trim the body at a paragraph boundary rather than cutting a URL in half.
        return safe_trim_article(shortened or text, MAX_ARTICLE_CHARS)
    except Exception:
        logger.exception("Article condensation failed; applying safe local trim")
        return safe_trim_article(text, MAX_ARTICLE_CHARS)


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
    context.user_data["admin_insert_mode"] = True
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
            await show_draft(query, context, fav_text, collapsed=True)
        except (ValueError, IndexError):
            await query.message.reply_text("Не вдалося відкрити цей матеріал.")
        return

    if query.data == "approve":
        try:
            await deliver_to_group(context.bot, draft)
            await clear_draft_messages(context.bot, user_id)
            PENDING_DRAFT.pop(user_id, None)
            context.user_data.pop("revision_edit", None)
            context.user_data.pop("manual_edit", None)
            context.user_data.pop("manual_parts", None)
            await query.message.reply_text("Готово. Матеріал підтверджено та відправлено в групу.")
        except Exception as exc:
            logger.exception("Publication failed")
            await query.message.reply_text(f"Не вдалося опублікувати: {type(exc).__name__}: {exc}")
        return

    if query.data == "revise":
        context.user_data["revision_edit"] = True
        context.user_data.pop("manual_edit", None)
        context.user_data.pop("manual_parts", None)
        await query.message.reply_text(
            "Напишіть одним повідомленням, що саме потрібно змінити. Я перероблю поточну версію. Власну думку, яку треба дослівно вставити, можна позначити [[ADMIN]]...[[/ADMIN]]."
        )
        return

    if query.data == "edit":
        context.user_data["manual_edit"] = True
        context.user_data["manual_parts"] = []
        context.user_data.pop("revision_edit", None)
        await query.message.reply_text(
            "Надішліть свій готовий текст замість цієї чернетки. "
            "Можна одним повідомленням або кількома частинами. Після останньої частини надішліть /done."
        )






async def text_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return

    user_id = update.effective_user.id

    if context.user_data.get("admin_insert_mode"):
        admin_text = update.message.text.strip()
        if not admin_text:
            return
        draft = PENDING_DRAFT.get(user_id)
        if not draft:
            context.user_data.pop("admin_insert_mode", None)
            await update.message.reply_text("Поточна чернетка вже відсутня.")
            return
        context.user_data.pop("admin_insert_mode", None)
        PENDING_DRAFT[user_id] = draft + "\n\n[[ADMIN]]" + admin_text + "[[/ADMIN]]"
        await update.message.reply_text(
            "Думку додано до чернетки. Для вставлення її в інше місце скористайтеся «Ввести свій текст» "
            "і маркерами [[ADMIN]]...[[/ADMIN]]."
        )
        await show_draft(update, context, PENDING_DRAFT[user_id], collapsed=True)
        return

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
    app.add_handler(CommandHandler("favorites", favorites_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
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
