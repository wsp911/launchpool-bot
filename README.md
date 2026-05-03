# 🚀 Launchpool Monitor Bot

Telegram-бот для мониторинга Launchpool-анонсов на Bybit, Bitget, Binance, Gate.io.
Запускается бесплатно через GitHub Actions каждые 10 минут.

---

## Установка за 5 шагов

### Шаг 1 — Создай Telegram-бота
1. Открой @BotFather в Telegram
2. Напиши `/newbot` и следуй инструкциям
3. Скопируй **токен** (выглядит как `123456789:AABBcc...`)

### Шаг 2 — Узнай свой Chat ID
1. Напиши боту @userinfobot в Telegram
2. Он вернёт твой `id` — это и есть Chat ID
   - Или напиши своему боту любое сообщение, затем открой:
   - `https://api.telegram.org/bot<ТВОЙ_ТОКЕН>/getUpdates`
   - Найди `"chat":{"id": ЧИСЛО}` — это и есть Chat ID

### Шаг 3 — Создай репозиторий на GitHub
1. Зайди на github.com → New repository
2. Назови его `launchpool-bot` (публичный или приватный — оба работают)
3. Загрузи все файлы из этой папки в репозиторий

### Шаг 4 — Добавь секреты (токены)
⚠️ НИКОГДА не вставляй токены прямо в код или коммиты!

1. Зайди в репозиторий → **Settings** → **Secrets and variables** → **Actions**
2. Нажми **New repository secret** и добавь два секрета:
   - `TELEGRAM_TOKEN` = токен от BotFather
   - `TELEGRAM_CHAT_ID` = твой chat_id

### Шаг 5 — Включи Actions и запусти
1. Перейди во вкладку **Actions** в репозитории
2. Найди workflow `Launchpool Monitor`
3. Нажми **Run workflow** для первого ручного запуска
4. Дальше он будет запускаться автоматически каждые 10 минут

---

## Как работает

```
GitHub Actions (cron каждые 10 мин)
        ↓
   bot.py запускается
        ↓
┌───────────────────────────────┐
│  Bybit API    (официальный)   │
│  Bitget API   (официальный)   │  → фильтр по ключевым словам
│  Binance bapi (неофициальный) │
│  Gate.io RSS  (парсинг)       │
└───────────────────────────────┘
        ↓
  Новый анонс? → Telegram уведомление
  Уже видели?  → Пропуск
        ↓
  seen_announcements.json обновляется (кэш GitHub Actions)
```

## Ключевые слова для фильтрации

Редактируй список `KEYWORDS` в `bot.py`:
```python
KEYWORDS = [
    "launchpool",
    "launch pool",
    "megadrop",          # Binance-специфичное
    "hodler airdrop",    # Binance-специфичное
    "stake to earn",
    "new pool",
    "farming",
    "earn campaign",
]
```

---

## Важные замечания

| Биржа | Тип источника | Надёжность |
|-------|--------------|------------|
| Bybit | Официальный API | ✅ Стабильно |
| Bitget | Официальный API | ✅ Стабильно |
| Binance | Неофициальный bapi | ⚠️ Может сломаться |
| Gate.io | RSS-лента | 🔄 Обычно работает |

- **GitHub Actions cron** может задерживаться до 10-15 мин при нагрузке — для Launchpool это ок
- Для более точного timing лучше использовать VPS с обычным cron

---

## Запуск локально (для теста)

```bash
pip install -r requirements.txt
export TELEGRAM_TOKEN="твой_токен"
export TELEGRAM_CHAT_ID="твой_chat_id"
python bot.py
```
