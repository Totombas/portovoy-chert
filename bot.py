
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

    with open(FLEET_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_fc_active_count(state, fc_key):
    return max(0, min(4, safe_int(state["fcs"][fc_key].get("active_subs", 0))))


def parse_iso_dt(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def parse_image(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))

    img = img.convert("L")
    img = img.resize((img.width * 4, img.height * 4))
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.SHARPEN)
    img = img.point(lambda x: 255 if x > 140 else 0)

    text = pytesseract.image_to_string(img, config="--psm 6")

    text = (
        text
        .replace("Om", "0m")
        .replace("Oh", "0h")
        .replace("Id", "1d")
        .replace("Ih", "1h")
        .replace("|d", "1d")
        .replace("l d", "1d")
        .replace("O m", "0m")
    )

    print("========== OCR ==========")
    print(text)
    print("=========================")

    voyage_lines = []

    for line in text.splitlines():
        clean = line.strip()

        if "Voyage complete in" in clean:
            voyage_lines.append(clean)

    result = []

    for line in voyage_lines:
        match = re.search(
            r"Voyage complete in\s*"
            r"(?:(\d+)d\s*)?"
            r"(?:(\d+)h\s*)?"
            r"(\d+)m",
            line,
            re.IGNORECASE,
        )

        if not match:
            continue

        days = int(match.group(1) or 0)
        hours = int(match.group(2) or 0)
        minutes = int(match.group(3))

        total_minutes = (
            days * 1440 +
            hours * 60 +
            minutes
        )

        result.append(
            now_utc() +
            timedelta(minutes=total_minutes)
        )

    return result


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
                f"### {idx}. {sub['name']}\n"
                f"{dot} —"
            )
            continue

        if mins == 0:
            lines.append(
                f"### {idx}. {sub['name']}\n"
                f"🟢 **ГОТОВО**"
            )
            continue

        and_time = to_andryukha_time(rt).strftime("%H:%M")
        val_time = to_valera_time(rt).strftime("%H:%M")

        lines.append(
            f"### {idx}. {sub['name']}\n"
            f"{dot} **{left}** • **{and_time} / {val_time}**"
        )

    return "\n".join(lines)


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


async def find_timer_dashboard_message(guild=None):
    global dashboard_message

    if dashboard_message is not None:
        return dashboard_message

    state = load_fleet_state()

    channel_id = state.get("dashboard_channel_id")
    message_id = state.get("dashboard_message_id")

    if channel_id and message_id:
        channel = client.get_channel(
            int(channel_id)
        )

        if channel is None:
            try:
                channel = await client.fetch_channel(
                    int(channel_id)
                )
            except Exception:
                channel = None

        if channel is not None:
            try:
                dashboard_message = await channel.fetch_message(
                    int(message_id)
                )
                return dashboard_message
            except Exception:
                dashboard_message = None

    if guild is None:
        return None

    timer_channel = None

    for channel in guild.text_channels:
        clean_name = channel.name.lower()

        if clean_name in TIMER_CHANNEL_NAMES:
            timer_channel = channel
            break

    if timer_channel is None:
        for channel in guild.text_channels:
            clean_name = channel.name.lower()

            if "таймер" in clean_name or "timer" in clean_name:
                timer_channel = channel
                break

    if timer_channel is None:
        return None

    try:
        async for msg in timer_channel.history(limit=50):
            if msg.author.id != client.user.id:
                continue

            if not msg.embeds:
                continue

            if (
                msg.embeds[0].title and
                (
                    "SUBMARINE COMMAND CENTER" in msg.embeds[0].title or
                    "ЛОДОЧКИ" in msg.embeds[0].title
                )
            ):
                dashboard_message = msg

                state["dashboard_message_id"] = msg.id
                state["dashboard_channel_id"] = msg.channel.id

                save_fleet_state(state)

                return dashboard_message

    except Exception as e:
        print("Dashboard search error:", e)

    return None


async def refresh_dashboard(channel=None, guild=None):
    global dashboard_message

    message = await find_timer_dashboard_message(guild)

    if guild is None:
        if message is not None:
            guild = message.guild
        elif channel is not None:
            guild = channel.guild

    embed = build_dashboard_embed(guild)
    view = FleetSelectView(guild=guild)

    if message is not None:
        try:
            await message.edit(
                embed=embed,
                view=view,
            )
            return message

        except Exception as e:
            print("Dashboard update error:", e)
            dashboard_message = None

    if channel is None:
        return None

    if guild is None:
        guild = channel.guild
        embed = build_dashboard_embed(guild)
        view = FleetSelectView(guild=guild)

    dashboard_message = await channel.send(
        embed=embed,
        view=view,
    )

    state = load_fleet_state()
    state["dashboard_message_id"] = dashboard_message.id
    state["dashboard_channel_id"] = dashboard_message.channel.id

    save_fleet_state(state)

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


async def send_ready_alert(channel, fc_key, sub_index, sub_name, rt):
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

    await refresh_dashboard(
        channel=channel,
        guild=channel.guild
    )

    await asyncio.sleep(86400)

    try:
        await msg.delete()
    except Exception:
        pass


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

            changed = False

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
                            changed = True

                            asyncio.create_task(
                                send_ready_alert(
                                    channel,
                                    fc_key,
                                    idx,
                                    sub["name"],
                                    rt
                                )
                            )

            if changed:
                save_fleet_state(state)

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


async def handle_scan_image(message, fc_key):
    if not message.attachments:
        return False

    attachment = message.attachments[0]
    lower_name = attachment.filename.lower()

    if not lower_name.endswith(
        (".png", ".jpg", ".jpeg")
    ):
        return False

    state = load_fleet_state()
    active = get_fc_active_count(
        state,
        fc_key
    )

    try:
        img_bytes = await attachment.read()
        new_times = parse_image(
            img_bytes
        )

        if not new_times:
            await message.add_reaction(
                "❌"
            )
            return True

        # Если в FC пока 0 лодок, первый нормальный скрин сам открывает слоты.
        if active <= 0:
            active = min(4, len(new_times))
            state["fcs"][fc_key]["active_subs"] = active

        if len(new_times) < active:
            await message.add_reaction(
                "❌"
            )
            return True

        fc = state["fcs"][fc_key]

        for idx, rt in enumerate(
            new_times[:active]
        ):
            fc["subs"][idx]["return_time"] = rt.isoformat()
            fc["subs"][idx]["ready_notified"] = False

        save_fleet_state(state)

        await refresh_dashboard(
            channel=message.channel,
            guild=message.guild
        )

        try:
            await message.delete()
        except Exception:
            pass

        print(f"Fleet updated: {fc_key}")

        return True

    except Exception as e:
        print("Scan error:", e)

        await message.add_reaction(
            "❌"
        )

        return True


@client.event
async def on_ready():
    print(f"Logged as {client.user}")

    client.add_view(
        FleetSelectView()
    )

    client.add_view(
        TreasuryView()
    )

    print("Bot ready")

    client.loop.create_task(
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
