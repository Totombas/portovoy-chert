
import io
import json
import re
import os
import asyncio
from datetime import datetime, timedelta

import discord
from discord import ui
from PIL import Image, ImageFilter, ImageOps
import pytesseract


TOKEN = os.getenv("DISCORD_TOKEN")

DATA_DIR = "data"
FLEET_FILE = os.path.join(DATA_DIR, "submarine_fleets.json")
TREASURY_FILE = os.path.join(DATA_DIR, "treasury.json")

UPDATE_INTERVAL = 15
SCAN_TIMEOUT_SECONDS = 120

ANDRYUKHA_OFFSET = 5
VALERA_OFFSET = 7

USER_IDS = [
    "259731173918507010",
    "293071176631189504",
]

TIMER_CHANNEL_NAMES = [
    "таймер",
    "timer",
]

pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# user_id -> {"fc_key": str, "expires_at": datetime}
pending_scans = {}
dashboard_message = None
dashboard_lock = asyncio.Lock()
updater_task = None


FC_CONFIG = {
    "eva": {
        "title": "E.V.A.",
        "short": "EVA",
        "emoji_name": "EVA",
        "fallback_emoji": "⚪",
        "color": 0xE5E5E5,
        "active_subs": 4,
        "subs": [
            "Dasha sledopit",
            "Moneymaker",
            "Cychka-lydoedka",
            "Free Ethernet",
        ],
    },
    "leviathan": {
        "title": "Leviathan",
        "short": "LEV",
        "emoji_name": "Leviathan",
        "fallback_emoji": "🌊",
        "color": 0x4DA6FF,
        "active_subs": 0,
        "subs": ["Leviathan-1", "Leviathan-2", "Leviathan-3", "Leviathan-4"],
    },
    "titan": {
        "title": "Titan",
        "short": "TIT",
        "emoji_name": "Titan",
        "fallback_emoji": "🪨",
        "color": 0xA97142,
        "active_subs": 0,
        "subs": ["Titan-1", "Titan-2", "Titan-3", "Titan-4"],
    },
    "garuda": {
        "title": "Garuda",
        "short": "GAR",
        "emoji_name": "Garuda",
        "fallback_emoji": "🪶",
        "color": 0x4CAF50,
        "active_subs": 0,
        "subs": ["Garuda-1", "Garuda-2", "Garuda-3", "Garuda-4"],
    },
    "ramuh": {
        "title": "Ramuh",
        "short": "RAM",
        "emoji_name": "Ramuh",
        "fallback_emoji": "⚡",
        "color": 0xFFD54F,
        "active_subs": 0,
        "subs": ["Ramuh-1", "Ramuh-2", "Ramuh-3", "Ramuh-4"],
    },
    "mog": {
        "title": "Mog",
        "short": "MOG",
        "emoji_name": "Mog",
        "fallback_emoji": "🌸",
        "color": 0xFF80AB,
        "active_subs": 0,
        "subs": ["Mog-1", "Mog-2", "Mog-3", "Mog-4"],
    },
    "ifrit": {
        "title": "Ifrit",
        "short": "IFR",
        "emoji_name": "Ifrit",
        "fallback_emoji": "🔥",
        "color": 0xF44336,
        "active_subs": 0,
        "subs": ["Ifrit-1", "Ifrit-2", "Ifrit-3", "Ifrit-4"],
    },
    "bahamut": {
        "title": "Bahamut",
        "short": "BAH",
        "emoji_name": "Bahamut",
        "fallback_emoji": "🐉",
        "color": 0x9C27B0,
        "active_subs": 0,
        "subs": ["Bahamut-1", "Bahamut-2", "Bahamut-3", "Bahamut-4"],
    },
}

FC_ALIASES = {
    "e.v.a.": "eva",
    "e.v.a": "eva",
    "eva": "eva",
    "эва": "eva",
    "основа": "eva",
    "main": "eva",
    "lev": "leviathan",
    "levi": "leviathan",
    "leviathan": "leviathan",
    "лев": "leviathan",
    "titan": "titan",
    "титан": "titan",
    "garuda": "garuda",
    "гаруда": "garuda",
    "ramuh": "ramuh",
    "рамух": "ramuh",
    "mog": "mog",
    "мог": "mog",
    "ifrit": "ifrit",
    "ифрит": "ifrit",
    "bahamut": "bahamut",
    "бахамут": "bahamut",
}


ITEMS = {
    "gold_necklace": {
        "title": "Ожерелье",
        "emoji_name": "Extravagant_salvaged_necklace",
        "price": 34500,
        "group": "gold",
    },
    "gold_earring": {
        "title": "Серьга",
        "emoji_name": "Extravagant_salvaged_earring",
        "price": 30000,
        "group": "gold",
    },
    "gold_bracelet": {
        "title": "Браслет",
        "emoji_name": "Extravagant_salvaged_bracelet",
        "price": 28500,
        "group": "gold",
    },
    "gold_ring": {
        "title": "Кольцо",
        "emoji_name": "Extravagant_salvaged_ring",
        "price": 27000,
        "group": "gold",
    },
    "silver_necklace": {
        "title": "Ожерелье",
        "emoji_name": "Salvaged_necklace",
        "price": 13000,
        "group": "silver",
    },
    "silver_earring": {
        "title": "Серьга",
        "emoji_name": "Salvaged_earring",
        "price": 10000,
        "group": "silver",
    },
    "silver_bracelet": {
        "title": "Браслет",
        "emoji_name": "Salvaged_bracelet",
        "price": 9000,
        "group": "silver",
    },
    "silver_ring": {
        "title": "Кольцо",
        "emoji_name": "Salvaged_ring",
        "price": 8000,
        "group": "silver",
    },
}

ITEM_ORDER = ["necklace", "earring", "bracelet", "ring"]

WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def weekday_ru(dt):
    return WEEKDAYS_RU[dt.weekday()]


def now_utc():
    return datetime.utcnow()


def to_andryukha_time(dt):
    return dt + timedelta(hours=ANDRYUKHA_OFFSET)


def to_valera_time(dt):
    return dt + timedelta(hours=VALERA_OFFSET)


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def format_gil(value):
    return f"{value:,}".replace(",", " ")


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def resolve_fc_key(raw):
    if not raw:
        return None
    return FC_ALIASES.get(raw.strip().lower())


def get_custom_emoji(guild, emoji_name):
    if guild is None:
        return None

    found = discord.utils.get(guild.emojis, name=emoji_name)

    if found:
        return str(found)

    return None


def get_fc_emoji(guild, fc_key):
    cfg = FC_CONFIG[fc_key]
    custom = get_custom_emoji(guild, cfg["emoji_name"])

    if custom:
        return custom

    return cfg["fallback_emoji"]


def default_fleet_state():
    return {
        "state_version": 3,
        "dashboard_message_id": None,
        "dashboard_channel_id": None,
        "fcs": {
            fc_key: {
                "active_subs": cfg["active_subs"],
                "subs": [
                    {
                        "name": sub_name,
                        "return_time": None,
                        "ready_notified": False,
                        "alert_message_id": None,
                        "alert_channel_id": None,
                    }
                    for sub_name in cfg["subs"]
                ],
            }
            for fc_key, cfg in FC_CONFIG.items()
        },
    }


def normalize_fleet_state(data):
    state = default_fleet_state()

    if not isinstance(data, dict):
        return state

    old_version = safe_int(data.get("state_version", 1), 1)

    state["dashboard_message_id"] = data.get("dashboard_message_id")
    state["dashboard_channel_id"] = data.get("dashboard_channel_id")

    old_fcs = data.get("fcs", {})
    if not isinstance(old_fcs, dict):
        return state

    for fc_key, cfg in FC_CONFIG.items():
        old_fc = old_fcs.get(fc_key, {})
        if not isinstance(old_fc, dict):
            continue

        old_subs = old_fc.get("subs", [])
        any_timer = False

        if isinstance(old_subs, list):
            for i in range(min(4, len(old_subs))):
                old_sub = old_subs[i]
                if not isinstance(old_sub, dict):
                    continue

                return_time = old_sub.get("return_time")
                state["fcs"][fc_key]["subs"][i]["return_time"] = return_time
                state["fcs"][fc_key]["subs"][i]["ready_notified"] = bool(
                    old_sub.get("ready_notified", False)
                )
                state["fcs"][fc_key]["subs"][i]["alert_message_id"] = old_sub.get(
                    "alert_message_id"
                )
                state["fcs"][fc_key]["subs"][i]["alert_channel_id"] = old_sub.get(
                    "alert_channel_id"
                )

                if return_time:
                    any_timer = True

        active = safe_int(old_fc.get("active_subs", cfg["active_subs"]), cfg["active_subs"])
        active = max(0, min(4, active))

        # Старые тестовые файлы могли создать Leviathan/Titan с активной лодкой.
        # При апгрейде до версии 3 сбрасываем пустые не-E.V.A. FC к дефолту.
        if old_version < 3 and fc_key != "eva" and not any_timer:
            active = cfg["active_subs"]

        state["fcs"][fc_key]["active_subs"] = active

    return state


def load_fleet_state():
    ensure_data_dir()

    if not os.path.exists(FLEET_FILE):
        state = default_fleet_state()
        save_fleet_state(state)
        return state

    try:
        with open(FLEET_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    state = normalize_fleet_state(data)
    save_fleet_state(state)
    return state


def save_fleet_state(state):
    ensure_data_dir()
    state["state_version"] = 3
    temp_file = FLEET_FILE + ".tmp"

    # Сначала полностью пишем временный файл, затем атомарно подменяем основной.
    # Так чтение никогда не увидит наполовину записанный JSON.
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())

    os.replace(temp_file, FLEET_FILE)


def save_dashboard_location(message_id, channel_id):
    """Меняет только адрес доски, не перезаписывая таймеры старой копией state."""
    state = load_fleet_state()
    state["dashboard_message_id"] = message_id
    state["dashboard_channel_id"] = channel_id
    save_fleet_state(state)


def apply_scanned_times(fc_key, active, new_times):
    """Записывает результат OCR поверх самого свежего состояния и проверяет запись."""
    expected_times = [
        rt.isoformat()
        for rt in new_times[:active]
    ]

    state = load_fleet_state()
    fc = state["fcs"][fc_key]
    fc["active_subs"] = active

    for idx, return_time in enumerate(expected_times):
        sub = fc["subs"][idx]
        sub["return_time"] = return_time
        sub["ready_notified"] = False
        sub["alert_message_id"] = None
        sub["alert_channel_id"] = None

    save_fleet_state(state)

    return scanned_times_match(
        fc_key,
        active,
        new_times,
    )


def scanned_times_match(fc_key, active, new_times):
    """Проверяет, что в файле остались именно таймеры принятого скрина."""
    expected_times = [
        rt.isoformat()
        for rt in new_times[:active]
    ]

    verified = load_fleet_state()
    verified_fc = verified["fcs"][fc_key]

    return (
        get_fc_active_count(verified, fc_key) == active and
        [
            sub.get("return_time")
            for sub in verified_fc["subs"][:active]
        ] == expected_times
    )


def get_fc_active_count(state, fc_key):
    return max(0, min(4, safe_int(state["fcs"][fc_key].get("active_subs", 0))))


def parse_iso_dt(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def normalize_ocr_text(text):
    """Исправляет типичные ошибки Tesseract именно в обозначениях времени."""
    return (
        text
        .replace("Om", "0m")
        .replace("Oh", "0h")
        .replace("Id", "1d")
        .replace("Ih", "1h")
        .replace("|d", "1d")
        .replace("l d", "1d")
        .replace("O m", "0m")
    )


def extract_voyage_minutes(text):
    """Возвращает длительности рейсов в том же порядке, что и на скрине."""
    text = normalize_ocr_text(text)

    # Ищем по всему тексту, а не только в строках с абсолютно точной фразой.
    # Tesseract иногда меняет регистр, добавляет лишние пробелы или читает m как rn.
    pattern = re.compile(
        r"voyage\s+complete\s+in\s*"
        r"(?:(\d+)\s*d\s*)?"
        r"(?:(\d+)\s*h\s*)?"
        r"(\d+)\s*(?:m|rn)\b",
        re.IGNORECASE,
    )

    result = []

    for match in pattern.finditer(text):
        days = int(match.group(1) or 0)
        hours = int(match.group(2) or 0)
        minutes = int(match.group(3))

        # Защита от случайных чисел, ошибочно принятых за таймер.
        if hours >= 24 or minutes >= 60:
            continue

        result.append(
            days * 1440 +
            hours * 60 +
            minutes
        )

    return result


def extract_deployed_count(text):
    match = re.search(
        r"vessels\s+deployed\s*:\s*([0-4])\s*/\s*4",
        text,
        re.IGNORECASE,
    )

    if match:
        return int(match.group(1))

    return None


def parse_image(image_bytes):
    source = Image.open(io.BytesIO(image_bytes)).convert("L")
    source = source.resize((source.width * 4, source.height * 4))
    source = ImageOps.autocontrast(source)
    source = source.filter(ImageFilter.SHARPEN)
    thresholded = source.point(lambda x: 255 if x > 140 else 0)

    # Один и тот же скрин прогоняем несколькими безопасными способами.
    # На небольшом Rank: 1 Tesseract иногда терял именно третью строку после
    # бинаризации, хотя глазами и в сыром OCR она была видна полностью.
    attempts = [
        (thresholded, "--psm 6"),
        (source, "--psm 6"),
        (thresholded, "--psm 11"),
    ]

    parsed_attempts = []

    for attempt_img, config in attempts:
        text = normalize_ocr_text(
            pytesseract.image_to_string(
                attempt_img,
                config=config,
            )
        )
        minutes = extract_voyage_minutes(text)
        deployed = extract_deployed_count(text)
        parsed_attempts.append((text, minutes, deployed))

    deployed_counts = [
        deployed
        for _, _, deployed in parsed_attempts
        if deployed is not None
    ]
    expected_count = max(deployed_counts) if deployed_counts else None

    # Предпочитаем вариант, где число найденных таймеров совпало с системной
    # строкой Vessels deployed. Если заголовок не прочитался — берём самый
    # результативный OCR-вариант.
    best_text, best_minutes, best_deployed = max(
        parsed_attempts,
        key=lambda item: (
            int(
                expected_count is not None and
                len(item[1]) == expected_count
            ),
            len(item[1]),
            int(item[2] == expected_count),
        ),
    )

    print("========== OCR ==========")
    print(best_text)
    print(
        "Parsed timers:",
        len(best_minutes),
        "deployed:",
        best_deployed,
    )
    print("=========================")

    scan_time = now_utc()

    return [
        scan_time + timedelta(minutes=minutes)
        for minutes in best_minutes[:4]
    ], expected_count


def get_ping_text():
    return " ".join(
        f"<@{i}>"
        for i in USER_IDS
    )


def format_remaining(rt):
    if rt is None:
        return "—", None

    delta = rt - now_utc()

    if delta.total_seconds() <= 0:
        return "ГОТОВО", 0

    mins = int(delta.total_seconds() // 60)

    if mins <= 0:
        return "<1м", 0

    d = mins // 1440
    h = (mins % 1440) // 60
    m = mins % 60

    if d:
        return f"{d}д {h:02}ч", mins

    if h:
        return f"{h:02}ч {m:02}м", mins

    return f"{m:02}м", mins


def status_dot(mins):
    if mins is None:
        return "⚫"

    if mins <= 0:
        return "🟢"

    if mins <= 360:
        return "🔵"

    if mins <= 720:
        return "🟡"

    if mins <= 1440:
        return "🟠"

    return "🔴"


def dashboard_color(state):
    all_mins = []

    for fc_key in FC_CONFIG:
        active = get_fc_active_count(state, fc_key)

        for sub in state["fcs"][fc_key]["subs"][:active]:
            rt = parse_iso_dt(sub.get("return_time"))
            _, mins = format_remaining(rt)

            if mins is not None:
                all_mins.append(mins)

    if any(m <= 0 for m in all_mins):
        return 0x2ECC71

    if not all_mins:
        return 0x5D6D7E

    nearest = min(all_mins)

    if nearest <= 360:
        return 0x00BFFF

    if nearest <= 720:
        return 0xF1C40F

    if nearest <= 1440:
        return 0xE67E22

    return 0xE74C3C


def get_ready_list(state):
    result = []

    for fc_key, cfg in FC_CONFIG.items():
        active = get_fc_active_count(state, fc_key)

        for idx, sub in enumerate(state["fcs"][fc_key]["subs"][:active], 1):
            rt = parse_iso_dt(sub.get("return_time"))
            _, mins = format_remaining(rt)

            if mins == 0:
                result.append(f"{cfg['short']}-{idx}")

    return result


def default_treasury():
    return {
        "inventory": {
            item_id: 0
            for item_id in ITEMS
        },
        "message_id": None,
        "channel_id": None,
        "updated_at": None,
    }


def load_treasury():
    ensure_data_dir()

    if not os.path.exists(TREASURY_FILE):
        data = default_treasury()
        save_treasury(data)
        return data

    try:
        with open(TREASURY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = default_treasury()

    if "inventory" not in data:
        data["inventory"] = {}

    for item_id in ITEMS:
        data["inventory"].setdefault(item_id, 0)

    data.setdefault("message_id", None)
    data.setdefault("channel_id", None)
    data.setdefault("updated_at", None)

    save_treasury(data)

    return data


def save_treasury(data):
    ensure_data_dir()

    with open(TREASURY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def item_total(data, item_id):
    return (
        int(data["inventory"].get(item_id, 0)) *
        int(ITEMS[item_id]["price"])
    )


def group_total(data, group):
    return sum(
        item_total(data, item_id)
        for item_id, item in ITEMS.items()
        if item["group"] == group
    )


def treasury_total():
    data = load_treasury()

    return (
        group_total(data, "gold") +
        group_total(data, "silver")
    )


def get_treasury_status():
    data = load_treasury()
    updated_at = data.get("updated_at")

    if not updated_at:
        return "⚠️ Нет данных", "—", 0xF1C40F

    updated_dt = parse_iso_dt(updated_at)

    if updated_dt is None:
        return "⚠️ Нет данных", "—", 0xF1C40F

    age_hours = (
        now_utc() - updated_dt
    ).total_seconds() / 3600

    local_time = to_andryukha_time(
        updated_dt
    ).strftime("%d.%m • %H:%M")

    if age_hours < 40:
        return "✅ В норме", local_time, 0x2ECC71

    if age_hours < 72:
        return "⚠️ Пора обновить", local_time, 0xF1C40F

    return "🚨 Старые данные", local_time, 0xE74C3C


def item_line(guild, data, item_id):
    item = ITEMS[item_id]

    emoji = get_custom_emoji(
        guild,
        item["emoji_name"]
    )

    if not emoji:
        emoji = "▫️"

    count = int(
        data["inventory"].get(item_id, 0)
    )

    total = item_total(
        data,
        item_id
    )

    return (
        f"{emoji} **{item['title']}** — "
        f"**{count}** шт. • "
        f"**{format_gil(total)}**"
    )


def build_treasury_embed(guild):
    data = load_treasury()

    gold_lines = [
        item_line(guild, data, f"gold_{kind}")
        for kind in ITEM_ORDER
    ]

    silver_lines = [
        item_line(guild, data, f"silver_{kind}")
        for kind in ITEM_ORDER
    ]

    gold_total = group_total(data, "gold")
    silver_total = group_total(data, "silver")
    total = gold_total + silver_total

    status_text, updated_text, color = get_treasury_status()

    embed = discord.Embed(
        title="📦 Склад FC",
        description="Текущее содержимое сундука компании.",
        color=color,
    )

    embed.add_field(
        name="🏅 Золото",
        value=(
            "\n".join(gold_lines) +
            f"\n\n**Итого золото:** `{format_gil(gold_total)}`"
        ),
        inline=False
    )

    embed.add_field(
        name="🥈 Серебро",
        value=(
            "\n".join(silver_lines) +
            f"\n\n**Итого серебро:** `{format_gil(silver_total)}`"
        ),
        inline=False
    )

    embed.add_field(
        name="💰 Общая сумма",
        value=f"**{format_gil(total)} gil**",
        inline=False
    )

    embed.add_field(
        name=status_text,
        value=f"🕒 Последнее обновление: `{updated_text}`",
        inline=False
    )

    return embed


def build_fc_field(state, fc_key):
    fc = state["fcs"][fc_key]
    active = get_fc_active_count(state, fc_key)

    if active <= 0:
        return "— лодок пока нет —"

    lines = []

    for idx, sub in enumerate(fc["subs"][:active], 1):
        rt = parse_iso_dt(sub.get("return_time"))
        left, mins = format_remaining(rt)
        dot = status_dot(mins)

        if rt is None:
            lines.append(
                f"**{idx}. {sub['name']}**"
                f"{dot} —"
            )
            continue

        if mins == 0:
            lines.append(
                f"**{idx}. {sub['name']}**"
                f"🟢 **ГОТОВО**\n"
            )
            continue

        and_dt = to_andryukha_time(rt)
        val_dt = to_valera_time(rt)

        and_time = f"{weekday_ru(and_dt)} {and_dt:%H:%M}"
        val_time = f"{weekday_ru(val_dt)} {val_dt:%H:%M}"

        lines.append(
            f"**{idx}. {sub['name']}**"
            f"{dot} **{left}**\n"
            f"🕒 **{and_time} / {val_time}**"
        )

    return "\n\n".join(lines)


def build_dashboard_embed(guild=None):
    state = load_fleet_state()
    ready = get_ready_list(state)

    treasury_status_text, treasury_updated_text, _ = get_treasury_status()
    total = treasury_total()

    embed = discord.Embed(
        title="🚢 ЛОДОЧКИ",
        description=(
            f"Обновлено: `{to_andryukha_time(now_utc()).strftime('%d.%m • %H:%M')}`"
        ),
        color=dashboard_color(state),
    )

    embed.add_field(
        name=f"🚨 Готовы: {len(ready)}",
        value=" • ".join(ready[:12]) if ready else "—",
        inline=True,
    )

    embed.add_field(
        name="📦 Склад",
        value=(
            f"`{format_gil(total)} gil`\n"
            f"{treasury_status_text}\n"
            f"`{treasury_updated_text}`"
        ),
        inline=True,
    )

    embed.add_field(
        name="​",
        value="​",
        inline=True,
    )

    for fc_key, cfg in FC_CONFIG.items():
        fc_emoji = get_fc_emoji(guild, fc_key)
        title = f"{fc_emoji} {cfg['title']}"

        embed.add_field(
            name=title,
            value=build_fc_field(state, fc_key),
            inline=True,
        )

    return embed


async def find_timer_dashboard_message(guild=None, cleanup_duplicates=True):
    global dashboard_message

    state = load_fleet_state()

    # Сначала пробуем сообщение, которое уже лежит в памяти.
    # Но дополнительно проверяем, что оно реально существует.
    if dashboard_message is not None:
        try:
            dashboard_message = await dashboard_message.channel.fetch_message(
                int(dashboard_message.id)
            )
        except Exception:
            dashboard_message = None

    channel = None

    channel_id = state.get("dashboard_channel_id")
    message_id = state.get("dashboard_message_id")

    if channel_id:
        channel = client.get_channel(int(channel_id))

        if channel is None:
            try:
                channel = await client.fetch_channel(int(channel_id))
            except Exception:
                channel = None

    # Если сохраненный ID сообщения валиден — используем его.
    if dashboard_message is None and channel is not None and message_id:
        try:
            dashboard_message = await channel.fetch_message(int(message_id))
        except Exception:
            dashboard_message = None

    # Если guild не передан, но канал известен, можем все равно почистить дубли.
    timer_channel = channel

    if timer_channel is None and guild is not None:
        for candidate in guild.text_channels:
            clean_name = candidate.name.lower()

            if clean_name in TIMER_CHANNEL_NAMES:
                timer_channel = candidate
                break

        if timer_channel is None:
            for candidate in guild.text_channels:
                clean_name = candidate.name.lower()

                if "таймер" in clean_name or "timer" in clean_name:
                    timer_channel = candidate
                    break

    if timer_channel is None:
        return dashboard_message

    found = []

    try:
        async for msg in timer_channel.history(limit=100):
            if msg.author.id != client.user.id:
                continue

            if not msg.embeds:
                continue

            title = msg.embeds[0].title or ""

            if (
                "SUBMARINE COMMAND CENTER" in title or
                "ЛОДОЧКИ" in title
            ):
                found.append(msg)

    except Exception as e:
        print("Dashboard search error:", e)
        return dashboard_message

    if not found:
        dashboard_message = None
        return None

    # Discord history идет от новых к старым. Оставляем самую свежую доску.
    found.sort(key=lambda msg: msg.created_at, reverse=True)
    newest = found[0]

    if cleanup_duplicates:
        for duplicate in found[1:]:
            try:
                await duplicate.delete()
                print(f"Deleted duplicate dashboard: {duplicate.id}")
            except Exception as e:
                print(f"Duplicate dashboard delete error {duplicate.id}:", e)

    dashboard_message = newest

    # После сетевых await исходный state уже мог устареть. Обновляем только ID
    # доски поверх свежего файла, чтобы не затереть только что принятый скрин.
    save_dashboard_location(
        newest.id,
        newest.channel.id,
    )

    return dashboard_message


async def refresh_dashboard(channel=None, guild=None, move_to_bottom=False):
    # Любые операции с инфодоской выполняются строго по одной.
    # Это не дает updater_loop, обработке скрина и уведомлению о готовности
    # одновременно удалить/создать несколько одинаковых сообщений.
    async with dashboard_lock:
        return await _refresh_dashboard_locked(
            channel=channel,
            guild=guild,
            move_to_bottom=move_to_bottom,
        )


async def _refresh_dashboard_locked(channel=None, guild=None, move_to_bottom=False):
    global dashboard_message

    message = await find_timer_dashboard_message(guild)

    if guild is None:
        if message is not None:
            guild = message.guild
        elif channel is not None:
            guild = channel.guild

    embed = build_dashboard_embed(guild)
    view = FleetSelectView(guild=guild)

    if message is not None and not move_to_bottom:
        try:
            await message.edit(
                embed=embed,
                view=view,
            )
            return message

        except Exception as e:
            print("Dashboard update error:", e)
            dashboard_message = None

    if message is not None and move_to_bottom:
        if channel is None:
            channel = message.channel

        try:
            await message.delete()
            dashboard_message = None
        except Exception as e:
            print("Dashboard move delete error:", e)

            # Если старое сообщение удалить не удалось, нельзя создавать новое —
            # иначе в чате останутся две инфодоски. Просто обновляем старую.
            try:
                await message.edit(
                    embed=embed,
                    view=view,
                )
                dashboard_message = message
                return message
            except Exception as edit_error:
                print("Dashboard fallback edit error:", edit_error)
                dashboard_message = None

    if channel is None:
        return None

    if guild is None:
        guild = channel.guild
        embed = build_dashboard_embed(guild)
        view = FleetSelectView(guild=guild)

    # Последняя проверка прямо перед созданием нового сообщения.
    # Если другая корутина уже успела создать доску, просто обновляем ее.
    existing = await find_timer_dashboard_message(
        guild,
        cleanup_duplicates=True,
    )

    if existing is not None:
        try:
            await existing.edit(
                embed=embed,
                view=view,
            )
            dashboard_message = existing
            return existing
        except Exception as e:
            print("Dashboard final recheck edit error:", e)
            dashboard_message = None

    dashboard_message = await channel.send(
        embed=embed,
        view=view,
    )

    save_dashboard_location(
        dashboard_message.id,
        dashboard_message.channel.id,
    )

    return dashboard_message


async def find_existing_treasury_message(channel):
    data = load_treasury()
    message_id = data.get("message_id")

    if message_id:
        try:
            msg = await channel.fetch_message(
                int(message_id)
            )

            if msg:
                return msg

        except Exception:
            pass

    found = None
    duplicates = []

    try:
        async for msg in channel.history(limit=50):
            if msg.author.id != client.user.id:
                continue

            if not msg.embeds:
                continue

            if msg.embeds[0].title != "📦 Склад FC":
                continue

            if found is None:
                found = msg
            else:
                duplicates.append(msg)

    except Exception as e:
        print("Treasury search error:", e)

    for duplicate in duplicates:
        try:
            await duplicate.delete()
        except Exception:
            pass

    if found:
        data["message_id"] = found.id
        data["channel_id"] = found.channel.id
        save_treasury(data)

    return found


async def refresh_treasury_message(interaction=None, channel=None):
    data = load_treasury()

    target_channel = (
        interaction.channel
        if interaction is not None
        else channel
    )

    if target_channel is None:
        return None

    embed = build_treasury_embed(
        target_channel.guild
    )

    view = TreasuryView()

    message = await find_existing_treasury_message(
        target_channel
    )

    if message:
        await message.edit(
            embed=embed,
            view=view
        )

    else:
        message = await target_channel.send(
            embed=embed,
            view=view
        )

        data["message_id"] = message.id
        data["channel_id"] = target_channel.id

        save_treasury(data)

    return message


class FleetSelectView(ui.View):

    def __init__(self, guild=None):
        super().__init__(
            timeout=None
        )

        state = load_fleet_state()
        fc_keys = list(FC_CONFIG)

        for fc_key, cfg in FC_CONFIG.items():
            active = get_fc_active_count(
                state,
                fc_key
            )

            row = (
                0
                if fc_keys.index(fc_key) < 4
                else 1
            )

            button = ui.Button(
                label=cfg["title"],
                emoji=get_fc_emoji(guild, fc_key),
                style=discord.ButtonStyle.secondary,
                custom_id=f"fleet_select:{fc_key}",
                row=row,
                disabled=False,
            )

            button.callback = self.make_select_callback(
                fc_key
            )

            self.add_item(button)

    def make_select_callback(self, fc_key):
        async def callback(interaction):
            pending_scans[interaction.user.id] = {
                "fc_key": fc_key,
                "expires_at": now_utc() + timedelta(
                    seconds=SCAN_TIMEOUT_SECONDS
                ),
            }

            cfg = FC_CONFIG[fc_key]
            emoji = get_fc_emoji(
                interaction.guild,
                fc_key
            )

            await interaction.response.send_message(
                (
                    f"{emoji} Жду скрин для "
                    f"**{cfg['title']}** "
                    f"{SCAN_TIMEOUT_SECONDS} сек."
                ),
                ephemeral=True,
                delete_after=10,
            )

        return callback


class GoldModal(ui.Modal):

    def __init__(self):
        super().__init__(
            title="🏅 Обновить золото"
        )

        inventory = load_treasury()["inventory"]

        self.necklace = ui.TextInput(
            label="Ожерелье",
            default=str(inventory.get("gold_necklace", 0)),
            required=True,
            max_length=4
        )

        self.earring = ui.TextInput(
            label="Серьга",
            default=str(inventory.get("gold_earring", 0)),
            required=True,
            max_length=4
        )

        self.bracelet = ui.TextInput(
            label="Браслет",
            default=str(inventory.get("gold_bracelet", 0)),
            required=True,
            max_length=4
        )

        self.ring = ui.TextInput(
            label="Кольцо",
            default=str(inventory.get("gold_ring", 0)),
            required=True,
            max_length=4
        )

        self.add_item(self.necklace)
        self.add_item(self.earring)
        self.add_item(self.bracelet)
        self.add_item(self.ring)

    async def on_submit(self, interaction):
        data = load_treasury()

        try:
            data["inventory"]["gold_necklace"] = int(str(self.necklace))
            data["inventory"]["gold_earring"] = int(str(self.earring))
            data["inventory"]["gold_bracelet"] = int(str(self.bracelet))
            data["inventory"]["gold_ring"] = int(str(self.ring))
            data["updated_at"] = now_utc().isoformat()

        except Exception:
            await interaction.response.send_message(
                "Нужно вводить только числа.",
                ephemeral=True,
                delete_after=10
            )
            return

        save_treasury(data)

        await interaction.response.defer(
            ephemeral=True
        )

        await refresh_treasury_message(
            interaction=interaction
        )

        await refresh_dashboard(
            guild=interaction.guild
        )


class SilverModal(ui.Modal):

    def __init__(self):
        super().__init__(
            title="🥈 Обновить серебро"
        )

        inventory = load_treasury()["inventory"]

        self.necklace = ui.TextInput(
            label="Ожерелье",
            default=str(inventory.get("silver_necklace", 0)),
            required=True,
            max_length=4
        )

        self.earring = ui.TextInput(
            label="Серьга",
            default=str(inventory.get("silver_earring", 0)),
            required=True,
            max_length=4
        )

        self.bracelet = ui.TextInput(
            label="Браслет",
            default=str(inventory.get("silver_bracelet", 0)),
            required=True,
            max_length=4
        )

        self.ring = ui.TextInput(
            label="Кольцо",
            default=str(inventory.get("silver_ring", 0)),
            required=True,
            max_length=4
        )

        self.add_item(self.necklace)
        self.add_item(self.earring)
        self.add_item(self.bracelet)
        self.add_item(self.ring)

    async def on_submit(self, interaction):
        data = load_treasury()

        try:
            data["inventory"]["silver_necklace"] = int(str(self.necklace))
            data["inventory"]["silver_earring"] = int(str(self.earring))
            data["inventory"]["silver_bracelet"] = int(str(self.bracelet))
            data["inventory"]["silver_ring"] = int(str(self.ring))
            data["updated_at"] = now_utc().isoformat()

        except Exception:
            await interaction.response.send_message(
                "Нужно вводить только числа.",
                ephemeral=True,
                delete_after=10
            )
            return

        save_treasury(data)

        await interaction.response.defer(
            ephemeral=True
        )

        await refresh_treasury_message(
            interaction=interaction
        )

        await refresh_dashboard(
            guild=interaction.guild
        )


class TreasuryView(ui.View):

    def __init__(self):
        super().__init__(
            timeout=None
        )

    @ui.button(
        label="Золото",
        emoji="🏅",
        style=discord.ButtonStyle.primary,
        custom_id="treasury_gold"
    )
    async def gold_button(self, interaction, button):
        await interaction.response.send_modal(
            GoldModal()
        )

    @ui.button(
        label="Серебро",
        emoji="🥈",
        style=discord.ButtonStyle.primary,
        custom_id="treasury_silver"
    )
    async def silver_button(self, interaction, button):
        await interaction.response.send_modal(
            SilverModal()
        )


async def delete_ready_alert(channel, sub):
    alert_message_id = sub.get("alert_message_id")

    alert_channel = channel
    alert_channel_id = sub.get("alert_channel_id")

    if alert_channel_id:
        alert_channel = client.get_channel(
            int(alert_channel_id)
        )

        if alert_channel is None:
            try:
                alert_channel = await client.fetch_channel(
                    int(alert_channel_id)
                )
            except Exception:
                alert_channel = channel

    deleted = False

    # Основной путь: удаляем сообщение по сохранённому ID.
    if alert_message_id:
        try:
            old_msg = await alert_channel.fetch_message(
                int(alert_message_id)
            )
            await old_msg.delete()
            deleted = True
        except Exception as e:
            print(
                f"Ready alert delete by ID error {alert_message_id}:",
                e
            )

    # Страховка для старых уведомлений, ID которых мог потеряться
    # из-за перезаписи состояния в updater_loop.
    if not deleted:
        try:
            async for msg in alert_channel.history(limit=100):
                if msg.author.id != client.user.id:
                    continue

                if not msg.embeds:
                    continue

                title = msg.embeds[0].title or ""

                if (
                    sub.get("name", "") in title and
                    "ГОТОВА" in title
                ):
                    await msg.delete()
                    deleted = True
                    print(
                        f"Deleted orphan ready alert: {msg.id} "
                        f"({sub.get('name')})"
                    )
                    break

        except Exception as e:
            print("Ready alert fallback search error:", e)

    sub["alert_message_id"] = None
    sub["alert_channel_id"] = None


async def cleanup_stale_ready_alerts(guild=None):
    """Удаляет старые уведомления ГОТОВА, которые уже не соответствуют состоянию лодок."""
    state = load_fleet_state()

    # Берём канал таймера из сохранённой доски.
    channel = None
    channel_id = state.get("dashboard_channel_id")

    if channel_id:
        channel = client.get_channel(int(channel_id))
        if channel is None:
            try:
                channel = await client.fetch_channel(int(channel_id))
            except Exception:
                channel = None

    if channel is None and guild is not None:
        for candidate in guild.text_channels:
            name = candidate.name.lower()
            if name in TIMER_CHANNEL_NAMES or "таймер" in name or "timer" in name:
                channel = candidate
                break

    if channel is None:
        return

    # Для каждой лодки определяем, должна ли сейчас существовать плашка ГОТОВА.
    expected_ready = {}
    for fc_key in FC_CONFIG:
        active = get_fc_active_count(state, fc_key)
        for sub in state["fcs"][fc_key]["subs"][:active]:
            rt = parse_iso_dt(sub.get("return_time"))
            _, mins = format_remaining(rt)
            expected_ready[sub["name"]] = (mins == 0)

    kept_ready = set()
    changed = False

    try:
        async for msg in channel.history(limit=200):
            if msg.author.id != client.user.id or not msg.embeds:
                continue

            title = msg.embeds[0].title or ""
            if "ГОТОВА" not in title:
                continue

            matched_name = next(
                (name for name in expected_ready if name in title),
                None,
            )
            if matched_name is None:
                continue

            should_exist = expected_ready[matched_name]

            # Если лодка уже перезапущена — уведомление устарело.
            # Если лодка всё ещё готова — оставляем только самое свежее уведомление.
            if not should_exist or matched_name in kept_ready:
                try:
                    await msg.delete()
                    print(f"Deleted stale ready alert on startup: {msg.id} ({matched_name})")
                except Exception as e:
                    print(f"Startup ready alert delete error {msg.id}:", e)
            else:
                kept_ready.add(matched_name)

    except Exception as e:
        print("Startup ready alert cleanup error:", e)

    # Чистим потерянные ID у уже запущенных лодок.
    for fc_key in FC_CONFIG:
        active = get_fc_active_count(state, fc_key)
        for sub in state["fcs"][fc_key]["subs"][:active]:
            rt = parse_iso_dt(sub.get("return_time"))
            _, mins = format_remaining(rt)
            if mins != 0 and (sub.get("alert_message_id") or sub.get("alert_channel_id")):
                sub["alert_message_id"] = None
                sub["alert_channel_id"] = None
                changed = True

    if changed:
        # За время обхода истории мог прийти новый скрин. Перечитываем файл и
        # чистим только служебные ID, не сохраняя устаревшие таймеры.
        latest_state = load_fleet_state()

        for fc_key in FC_CONFIG:
            active = get_fc_active_count(latest_state, fc_key)
            for sub in latest_state["fcs"][fc_key]["subs"][:active]:
                rt = parse_iso_dt(sub.get("return_time"))
                _, mins = format_remaining(rt)

                if mins != 0:
                    sub["alert_message_id"] = None
                    sub["alert_channel_id"] = None

        save_fleet_state(latest_state)


async def send_ready_alert(
    channel,
    fc_key,
    sub_index,
    sub_name,
    rt,
):
    cfg = FC_CONFIG[fc_key]
    emoji = get_fc_emoji(
        channel.guild,
        fc_key
    )

    embed = discord.Embed(
        title=(
            f"🚨 {emoji} {cfg['title']} • "
            f"{sub_name} ГОТОВА"
        ),
        color=0x2ECC71,
    )

    embed.add_field(
        name="Андрюха",
        value=to_andryukha_time(rt).strftime("%H:%M"),
        inline=True
    )

    embed.add_field(
        name="Валера",
        value=to_valera_time(rt).strftime("%H:%M"),
        inline=True
    )

    embed.add_field(
        name="Статус",
        value="💰 +БАБКИ, ЗАПУСКАЙ ПО НОВОЙ 💰",
        inline=False
    )

    msg = await channel.send(
        get_ping_text(),
        embed=embed
    )

    # Отправка сообщения содержит await, поэтому перед сохранением обязательно
    # перечитываем состояние. Иначе updater мог вернуть старые таймеры поверх
    # только что обработанного скрина.
    latest_state = load_fleet_state()
    sub = latest_state["fcs"][fc_key]["subs"][sub_index - 1]

    # Пока уведомление отправлялось, лодку могли уже перезапустить новым скрином.
    if sub.get("return_time") != rt.isoformat():
        try:
            await msg.delete()
        except Exception:
            pass
        return

    sub["ready_notified"] = True
    sub["alert_message_id"] = msg.id
    sub["alert_channel_id"] = msg.channel.id
    save_fleet_state(latest_state)

    await refresh_dashboard(
        channel=channel,
        guild=channel.guild,
        move_to_bottom=True,
    )


async def updater_loop():
    await client.wait_until_ready()

    while not client.is_closed():
        try:
            message = await find_timer_dashboard_message(None)
            if message is not None:
                await refresh_dashboard(
                    channel=message.channel,
                    guild=message.guild,
                )
            else:
                await refresh_dashboard()

            state = load_fleet_state()
            message = await find_timer_dashboard_message(None)
            channel = (
                message.channel
                if message is not None
                else None
            )

            if channel is not None:
                for fc_key, cfg in FC_CONFIG.items():
                    active = get_fc_active_count(
                        state,
                        fc_key
                    )

                    for idx, sub in enumerate(
                        state["fcs"][fc_key]["subs"][:active],
                        1
                    ):
                        rt = parse_iso_dt(
                            sub.get("return_time")
                        )

                        if rt is None:
                            continue

                        if (
                            not sub.get("ready_notified") and
                            now_utc() >= rt
                        ):
                            sub["ready_notified"] = True

                            # send_ready_alert после отправки перечитает свежий
                            # state и добавит только ID уведомления. Это не даёт
                            # циклу затереть таймеры нового скрина старой копией.
                            await send_ready_alert(
                                channel,
                                fc_key,
                                idx,
                                sub["name"],
                                rt,
                            )

            try:
                treasury_data = load_treasury()
                treasury_channel_id = treasury_data.get("channel_id")

                if treasury_channel_id:
                    treasury_channel = client.get_channel(
                        int(treasury_channel_id)
                    )

                    if treasury_channel is None:
                        try:
                            treasury_channel = await client.fetch_channel(
                                int(treasury_channel_id)
                            )
                        except Exception:
                            treasury_channel = None

                    if treasury_channel is not None:
                        await refresh_treasury_message(
                            channel=treasury_channel
                        )

            except Exception as e:
                print("Treasury auto-refresh error:", e)

        except Exception as e:
            print("Loop error:", e)

        await asyncio.sleep(
            UPDATE_INTERVAL
        )


async def report_scan_error(message, reason):
    """Явно сообщает об ошибке и оставляет режим ожидания скрина активным."""
    try:
        await message.add_reaction("❌")
    except Exception:
        pass

    try:
        await message.reply(
            f"❌ Скрин не принят: {reason}",
            mention_author=False,
            delete_after=20,
        )
    except Exception as e:
        print("Scan error reply failed:", e)

    pending = pending_scans.get(message.author.id)
    if pending:
        pending["expires_at"] = now_utc() + timedelta(
            seconds=SCAN_TIMEOUT_SECONDS
        )


async def handle_scan_image(message, fc_key):
    if not message.attachments:
        return False

    attachment = message.attachments[0]
    lower_name = attachment.filename.lower()

    if not lower_name.endswith(
        (".png", ".jpg", ".jpeg")
    ):
        return False

    try:
        img_bytes = await attachment.read()
        new_times, deployed_count = parse_image(
            img_bytes
        )

        if not new_times:
            await report_scan_error(
                message,
                "не удалось распознать ни одного таймера. "
                "Исходный скрин оставлен, можно сразу прислать следующий.",
            )
            return False

        # Строка Vessels deployed на скрине — главный источник количества лодок.
        # Старое active_subs могло быть больше/меньше и раньше из-за этого бот
        # отклонял даже корректный скрин с тремя полностью распознанными таймерами.
        found = min(4, len(new_times))

        if deployed_count is not None:
            deployed_count = max(0, min(4, deployed_count))

            # Заголовок говорит, сколько строк обязано быть распознано. Если
            # таймеров меньше — не записываем неполные или сдвинутые данные.
            if found != deployed_count:
                print(
                    "Scan rejected: timers/header mismatch",
                    found,
                    deployed_count,
                )
                await report_scan_error(
                    message,
                    (
                        f"в заголовке лодок {deployed_count}, "
                        f"а таймеров прочитано {found}. "
                        "Исходный скрин не удалён."
                    ),
                )
                return False

            active = deployed_count
        else:
            # Запасной путь для скрина, где заголовок не попал в кадр.
            state = load_fleet_state()
            active = get_fc_active_count(
                state,
                fc_key
            )

            if found > active:
                active = found

            if found < active:
                await report_scan_error(
                    message,
                    (
                        f"прочитано только {found} из {active} таймеров. "
                        "Исходный скрин не удалён."
                    ),
                )
                return False

        # Снимок нужен только для удаления старых уведомлений. После всех await
        # состояние будет перечитано заново перед фактической записью таймеров.
        state_snapshot = load_fleet_state()
        fc_snapshot = state_snapshot["fcs"][fc_key]

        for idx, rt in enumerate(
            new_times[:active]
        ):
            await delete_ready_alert(
                message.channel,
                fc_snapshot["subs"][idx]
            )

        if not apply_scanned_times(
            fc_key,
            active,
            new_times,
        ):
            await report_scan_error(
                message,
                "таймеры не прошли проверку после записи. Скрин не удалён.",
            )
            return False

        await refresh_dashboard(
            channel=message.channel,
            guild=message.guild,
            move_to_bottom=True,
        )

        # Проверяем ещё раз после сетевого обновления доски: именно здесь раньше
        # редкая параллельная запись могла молча вернуть старые таймеры.
        if not scanned_times_match(
            fc_key,
            active,
            new_times,
        ):
            await report_scan_error(
                message,
                "другая операция перезаписала таймеры. Скрин сохранён для повтора.",
            )
            return False

        try:
            await message.delete()
        except Exception:
            pass

        print(f"Fleet updated: {fc_key}")

        return True

    except Exception as e:
        print("Scan error:", e)

        await report_scan_error(
            message,
            f"внутренняя ошибка `{type(e).__name__}`. Скрин не удалён.",
        )

        return False


@client.event
async def on_ready():
    global updater_task

    print(f"Logged as {client.user}")

    client.add_view(
        FleetSelectView()
    )

    client.add_view(
        TreasuryView()
    )

    print("Bot ready")

    # После рестарта сразу убираем старые плашки ГОТОВА
    # для лодок, которые уже были запущены заново.
    try:
        guild = client.guilds[0] if client.guilds else None
        await cleanup_stale_ready_alerts(guild)
    except Exception as e:
        print("Initial ready alert cleanup error:", e)

    # on_ready может вызываться повторно после переподключения Discord.
    # Не запускаем второй updater_loop поверх уже работающего.
    if updater_task is None or updater_task.done():
        updater_task = asyncio.create_task(
            updater_loop()
        )


@client.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.strip()
    low = content.lower()

    if low in [
        "!dashboard",
        "!dash",
        "!таймер",
        "!timer",
        "!subs",
    ]:
        await refresh_dashboard(
            channel=message.channel,
            guild=message.guild
        )

        try:
            await message.delete()
        except Exception:
            pass

        return

    if low in [
        "!treasury",
        "!склад",
        "!fc",
    ]:
        await refresh_treasury_message(
            channel=message.channel
        )

        try:
            await message.delete()
        except Exception:
            pass

        return

    # Быстрый ручной выбор без кнопки: !scan leviathan
    if (
        low.startswith("!scan ") or
        low.startswith("!скан ")
    ):
        raw_fc = content.split(
            maxsplit=1
        )[1]

        fc_key = resolve_fc_key(
            raw_fc
        )

        if fc_key is None:
            await message.add_reaction(
                "❌"
            )
            return

        pending_scans[message.author.id] = {
            "fc_key": fc_key,
            "expires_at": now_utc() + timedelta(
                seconds=SCAN_TIMEOUT_SECONDS
            ),
        }

        try:
            await message.delete()
        except Exception:
            pass

        return

    # Меняем количество активных лодок: !slots leviathan 2
    if (
        low.startswith("!slots ") or
        low.startswith("!лодки ")
    ):
        parts = content.split()

        if len(parts) != 3:
            await message.add_reaction(
                "❌"
            )
            return

        fc_key = resolve_fc_key(
            parts[1]
        )

        count = safe_int(
            parts[2],
            -1
        )

        if (
            fc_key is None or
            count < 0 or
            count > 4
        ):
            await message.add_reaction(
                "❌"
            )
            return

        state = load_fleet_state()
        state["fcs"][fc_key]["active_subs"] = count

        save_fleet_state(state)

        await refresh_dashboard(
            channel=message.channel,
            guild=message.guild
        )

        try:
            await message.delete()
        except Exception:
            pass

        return

    if message.attachments:
        pending = pending_scans.get(
            message.author.id
        )

        if (
            pending and
            now_utc() <= pending["expires_at"]
        ):
            fc_key = pending["fc_key"]

            handled = await handle_scan_image(
                message,
                fc_key
            )

            if handled:
                pending_scans.pop(
                    message.author.id,
                    None
                )
                return

        elif pending:
            pending_scans.pop(
                message.author.id,
                None
            )


if TOKEN is None:
    raise RuntimeError(
        "DISCORD_TOKEN is not set"
    )

client.run(TOKEN)
