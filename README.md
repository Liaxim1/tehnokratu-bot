# Технократ — Telegram-бот

Бот готує щотижневі аналітичні матеріали для «Технократа», надсилає їх адміністратору на погодження і публікує лише після підтвердження.

## Чому ця версія придатна для Railway Free

Бот більше не тримає постійний процес опитування Telegram і не використовує внутрішній планувальник Railway.

- Telegram працює через webhook: сервіс прокидається лише коли приходить запит.
- Railway Serverless може присипляти неактивний сервіс, що зменшує споживання ресурсів.
- Щосуботи GitHub Actions запускає захищений endpoint `/internal/weekly`, який будить Railway і запускає підготовку огляду.
- Чернетка та «Обране» зберігаються у `state.json`. Для цього на Railway потрібно підключити Volume з точкою монтування `/data`.

## Команди

- `/post` — створити статтю для погодження;
- `/preview` — те саме, без автоматичної публікації;
- `/ask [питання]` — окремий аналіз;
- `/cancel` — скасувати поточну чернетку;
- `/favorites` — відкрити «Обране»;
- `/admin` — додати власну думку до поточної чернетки;
- `/done` — завершити ручне введення;
- `/start` і `/help` — довідка.

Публікація відбувається тільки після натискання «Підтвердити і відправити».

## Змінні Railway

Обов'язкові:

```text
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.6-luna
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHANNEL_ID=@your_channel
ADMIN_ID=123456789
SCHEDULE_SECRET=довгий-випадковий-рядок
STATE_DIR=/data
```

Railway автоматично надає `RAILWAY_PUBLIC_DOMAIN`; бот використовує його для Telegram webhook.

## Налаштування Railway

1. Відкрийте сервіс `tehnokratu-bot`.
2. Перейдіть у Settings → Volumes і створіть один Volume, змонтувавши його в `/data`.
3. У Settings → Deploy → Serverless увімкніть Serverless.
4. Переконайтеся, що сервіс має Railway service domain.
5. Після нового деплою webhook встановиться автоматично.

## Налаштування GitHub Actions

У репозиторії створено `.github/workflows/weekly.yml`.

У Settings → Secrets and variables → Actions → New repository secret створіть:

- `RAILWAY_BOT_URL` — повна адреса сервісу Railway, наприклад `https://ваш-домен.up.railway.app`;
- `SCHEDULE_SECRET` — той самий секрет, який задано в Railway.

Workflow запускається щосуботи о 10:00 за київським часом і має також кнопку ручного запуску `Run workflow`.

## Локальний запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

Для локального запуску Telegram webhook потребує доступної з інтернету HTTPS-адреси. На Railway це налаштовується автоматично через `RAILWAY_PUBLIC_DOMAIN`.
