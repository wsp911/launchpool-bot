"""
Launchpool Monitor Bot
Мониторит анонсы Launchpool на Bybit, Bitget, Binance, Gate.io
и отправляет уведомления в Telegram.

Запуск:
  python bot.py          — обычный режим мониторинга
  python bot.py --test   — отправить тестовое сообщение и проверить соединение
"""

import os
import sys
import json
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import requests

# ══════════════════════════════════════════════
#  КОНФИГУРАЦИЯ — читается из переменных среды
# ══════════════════════════════════════════════
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

SEEN_FILE = "seen_announcements.json"

KEYWORDS = [
    "launchpool",
    "launch pool",
    "megadrop",
    "hodler airdrop",
    "stake to earn",
    "new pool",
    "farming",
    "earn campaign",
]


# ══════════════════════════════════════════════
#  УТИЛИТЫ
# ══════════════════════════════════════════════

def load_seen() -> set:
    if Path(SEEN_FILE).exists():
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f, indent=2)


def make_id(*parts) -> str:
    return hashlib.md5("_".join(str(p) for p in parts).encode()).hexdigest()


def is_launchpool(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in KEYWORDS)


def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        print(f"  -> Telegram OK")
    except Exception as e:
        print(f"  Telegram ошибка: {e}")


def format_message(ann: dict) -> str:
    emoji_map = {
        "Binance": "🟡",
        "Bybit":   "🟠",
        "Bitget":  "🔵",
        "Gate.io": "🟢",
    }
    emoji = emoji_map.get(ann["exchange"], "⚪")
    now   = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    return (
        f"{emoji} <b>{ann['exchange']} — Launchpool!</b>\n\n"
        f"📋 {ann['title']}\n\n"
        f"🔗 <a href='{ann['url']}'>Открыть →</a>\n"
        f"🕐 {now}"
    )


# ══════════════════════════════════════════════
#  ПАРСЕРЫ БИРЖ
# ══════════════════════════════════════════════

def check_bybit() -> list:
    """Bybit — официальный публичный endpoint анонсов."""
    results = []
    try:
        url    = "https://api.bybit.com/v5/announcements/index"
        params = {"locale": "en-US", "page": 1, "limit": 20}
        r      = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data   = r.json()

        items = data.get("result", {}).get("list", [])
        for item in items:
            title  = item.get("title", "")
            link   = item.get("url", "")
            ann_id = make_id("bybit", item.get("id", title))

            if is_launchpool(title):
                results.append({
                    "id":       ann_id,
                    "exchange": "Bybit",
                    "title":    title,
                    "url":      link,
                })

        print(f"Bybit: проверено {len(items)} анонсов, найдено {len(results)}")
    except Exception as e:
        print(f"Bybit ошибка: {e}")
    return results


def check_bitget() -> list:
    """
    Bitget — ДВА источника:
    1. API анонсов — ловит новости с ключевыми словами
    2. API страницы Launchpool — ловит активные пулы напрямую,
       даже если анонс ещё не вышел или называется иначе
    """
    results = []

    # --- Источник 1: анонсы ---
    try:
        url    = "https://api.bitget.com/api/v2/public/annc/list"
        params = {"language": "en_US", "size": 20}
        r      = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data   = r.json()

        items = data.get("data", {}).get("items", [])
        for item in items:
            title  = item.get("title", "")
            link   = item.get("url", "")
            ann_id = make_id("bitget_ann", item.get("id", title))

            if is_launchpool(title):
                results.append({
                    "id":       ann_id,
                    "exchange": "Bitget",
                    "title":    title,
                    "url":      link,
                })
        print(f"Bitget анонсы: проверено {len(items)}, найдено {len(results)}")
    except Exception as e:
        print(f"Bitget анонсы ошибка: {e}")

    # --- Источник 2: прямой API активных пулов ---
    # Новый пул появляется здесь раньше чем выходит анонс!
    try:
        url     = "https://api.bitget.com/api/v2/earn/launchpool/list"
        params  = {"status": "ongoing", "pageSize": 10}
        headers = {"User-Agent": "Mozilla/5.0 (compatible; LaunchpoolBot/1.0)"}
        r       = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data    = r.json()

        # API может вернуть data как список или как объект с items
        raw = data.get("data", [])
        pools = raw if isinstance(raw, list) else raw.get("items", [])

        for pool in pools:
            name   = pool.get("coinName") or pool.get("projectName") or pool.get("name", "")
            pid    = pool.get("projectId") or pool.get("id") or name
            title  = f"Bitget Launchpool: {name} — новый пул открыт!"
            link   = "https://www.bitget.com/events/launchpool"
            ann_id = make_id("bitget_pool", pid)

            if name:
                results.append({
                    "id":       ann_id,
                    "exchange": "Bitget",
                    "title":    title,
                    "url":      link,
                })

        print(f"Bitget пулы: найдено активных {len(pools)}")
    except Exception as e:
        print(f"Bitget пулы ошибка: {e}")

    return results


def check_binance() -> list:
    """
    Binance — неофициальный bapi endpoint.
    Фильтруем: launchpool, megadrop, hodler airdrop и т.д.
    """
    results = []
    try:
        url     = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
        params  = {"type": 1, "pageNo": 1, "pageSize": 20}
        headers = {"User-Agent": "Mozilla/5.0 (compatible; LaunchpoolBot/1.0)"}

        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()

        catalogs = data.get("data", {}).get("catalogs", [])
        all_articles = []
        for catalog in catalogs:
            all_articles.extend(catalog.get("articles", []))

        for article in all_articles:
            title  = article.get("title", "")
            code   = article.get("code", "")
            link   = f"https://www.binance.com/en/support/announcement/{code}"
            ann_id = make_id("binance", code or title)

            if is_launchpool(title):
                results.append({
                    "id":       ann_id,
                    "exchange": "Binance",
                    "title":    title,
                    "url":      link,
                })

        print(f"Binance: проверено {len(all_articles)} анонсов, найдено {len(results)}")
    except Exception as e:
        print(f"Binance ошибка: {e}")
    return results


def check_gateio() -> list:
    """Gate.io — RSS лента новостей."""
    results = []
    try:
        url     = "https://www.gate.io/en/rss/article"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; LaunchpoolBot/1.0)"}

        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()

        root    = ET.fromstring(r.content)
        channel = root.find("channel")
        if channel is None:
            print("Gate.io: RSS канал не найден")
            return results

        items = channel.findall("item")[:20]
        for item in items:
            title  = item.findtext("title", "").strip()
            link   = item.findtext("link",  "").strip()
            ann_id = make_id("gateio", link or title)

            if is_launchpool(title):
                results.append({
                    "id":       ann_id,
                    "exchange": "Gate.io",
                    "title":    title,
                    "url":      link,
                })

        print(f"Gate.io: проверено {len(items)} анонсов, найдено {len(results)}")
    except Exception as e:
        print(f"Gate.io ошибка: {e}")
    return results


# ══════════════════════════════════════════════
#  ТЕСТОВЫЙ РЕЖИМ
# ══════════════════════════════════════════════

def test_mode():
    print(f"\n{'='*50}")
    print(f"ТЕСТОВЫЙ РЕЖИМ | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*50}")

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Не заданы TELEGRAM_TOKEN или TELEGRAM_CHAT_ID!")
        sys.exit(1)

    print(f"TELEGRAM_TOKEN найден (длина: {len(TELEGRAM_TOKEN)} символов)")
    print(f"TELEGRAM_CHAT_ID найден: {TELEGRAM_CHAT_ID}")

    print("\nПроверяю бота через Telegram API...")
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe",
            timeout=10
        )
        data = r.json()
        if data.get("ok"):
            bot_name = data["result"].get("username", "???")
            print(f"Бот найден: @{bot_name}")
        else:
            print(f"Ошибка: {data.get('description', 'неизвестная ошибка')}")
            print("Скорее всего токен неправильный. Проверь TELEGRAM_TOKEN.")
            sys.exit(1)
    except Exception as e:
        print(f"Не могу подключиться к Telegram: {e}")
        sys.exit(1)

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    test_message = (
        f"🧪 <b>Это тестовое сообщение!</b>\n\n"
        f"Если ты это видишь — бот настроен правильно ✅\n\n"
        f"Вот как будет выглядеть реальное уведомление:\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🟡 <b>Binance — Launchpool!</b>\n\n"
        f"📋 Binance Launchpool: New TOKEN! Farm & Earn Rewards\n\n"
        f"🔗 <a href='https://www.binance.com'>Открыть анонс →</a>\n"
        f"🕐 {now}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Бот проверяет биржи каждые 10 минут 🔄"
    )

    print("\nОтправляю тестовое сообщение в Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": test_message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        data = r.json()
        if data.get("ok"):
            print("Тестовое сообщение отправлено! Проверь Telegram.")
        else:
            print(f"Ошибка отправки: {data.get('description', '???')}")
            if "chat not found" in str(data).lower():
                print("Похоже Chat ID неправильный. Напиши боту /start и попробуй снова.")
            sys.exit(1)
    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)

    print(f"\n{'='*50}")
    print("Тест пройден успешно! Бот готов к работе.")
    print(f"{'='*50}\n")


# ══════════════════════════════════════════════
#  ОСНОВНОЙ ЗАПУСК
# ══════════════════════════════════════════════

def main():
    print(f"\n{'='*50}")
    print(f"Launchpool Monitor | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*50}")

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Не заданы TELEGRAM_TOKEN или TELEGRAM_CHAT_ID!")
        return

    seen = load_seen()
    print(f"Загружено {len(seen)} уже обработанных анонсов\n")

    all_announcements = []
    all_announcements += check_bybit()
    all_announcements += check_bitget()
    all_announcements += check_binance()
    all_announcements += check_gateio()

    print(f"\nИтого найдено Launchpool-анонсов: {len(all_announcements)}")

    new_count = 0
    for ann in all_announcements:
        if ann["id"] not in seen:
            seen.add(ann["id"])
            print(f"\nНовый: [{ann['exchange']}] {ann['title']}")
            send_telegram(format_message(ann))
            new_count += 1
        else:
            print(f"  Уже отправлено: {ann['title'][:60]}...")

    save_seen(seen)
    print(f"\nГотово. Новых уведомлений отправлено: {new_count}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    if "--test" in sys.argv:
        test_mode()
    else:
        main()
