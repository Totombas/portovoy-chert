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

SAVE_FILE = "submarines.json"

DATA_DIR = "data"
TREASURY_FILE = os.path.join(DATA_DIR, "treasury.json")

UPDATE_INTERVAL = 15

ANDRYUKHA_OFFSET = 5
VALERA_OFFSET = 7

USER_IDS = [
    "259731173918507010",
    "293071176631189504",
]

pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

dashboard_message = None
return_times = []
ready_sent = []


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

ITEM_ORDER = [
    "necklace",
    "earring",
    "bracelet",
    "ring",
]


def now_utc():
    return datetime.utcnow()


def to_andryukha_time(dt):
    return dt + timedelta(hours=ANDRYUKHA_OFFSET)


def to_valera_time(dt):
    return dt + timedelta(hours=VALERA_OFFSET)


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def save_times(times):
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            [x.isoformat() for x in times],
            f,
            ensure_ascii=False,
            indent=2
        )


def load_times():
    try:
        with open(SAVE_FILE, encoding="utf-8") as f:
            return [
                datetime.fromisoformat(x)
                for x in json.load(f)
            ]
    except:
        return []


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
    except:
        data = default_treasury()

    if "inventory" not in data:
        data["inventory"] = {}

    for item_id in ITEMS:
        if item_id not in data["inventory"]:
            data["inventory"][item_id] = 0

    if "message_id" not in data:
        data["message_id"] = None

    if "channel_id" not in data:
        data["channel_id"] = None

    if "updated_at" not in data:
        data["updated_at"] = None

    save_treasury(data)

    return data


def save_treasury(data):
    ensure_data_dir()

    with open(TREASURY_FILE, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


def parse_image(image_bytes):
    img = Image.open(
        io.BytesIO(image_bytes)
    )

    img = img.convert("L")

    img = img.resize(
        (
            img.width * 4,
            img.height * 4
        )
    )

    img = ImageOps.autocontrast(img)

    img = img.filter(
        ImageFilter.SHARPEN
    )

    img = img.point(
        lambda x: 255 if x > 140 else 0
    )

    text = pytesseract.image_to_string(
        img,
        config="--psm 6"
    )

    text = (
        text
        .replace("Om", "0m")
        .replace("Oh", "0h")
        .replace("Id", "1d")
        .replace("Ih", "1h")
    )

    print("========== OCR ==========")
    print(text)
    print("=========================")

    voyage_lines = []

    for line in text.splitlines():
        if "Voyage complete in" in line:
            voyage_lines.append(line)

    result = []

    for line in voyage_lines:
        match = re.search(
            r"Voyage complete in\s*"
            r"(?:(\d+)d\s*)?"
            r"(?:(\d+)h\s*)?"
            r"(\d+)m",
            line
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
            timedelta(
                minutes=total_minutes
            )
        )

    return result


def get_ping_text():
    return " ".join(
        f"<@{i}>"
        for i in USER_IDS
    )


def format_remaining(rt):
    delta = rt - now_utc()

    if delta.total_seconds() <= 0:
        return "ГОТОВО ✅", 0

    mins = int(
        delta.total_seconds() // 60
    )

    if mins <= 0:
        return "<1 мин", 0

    d = mins // 1440
    h = (mins % 1440) // 60
    m = mins % 60

    if d:
        return (
            f"{d}д {h}ч {m}м",
            mins
        )

    return (
        f"{h}ч {m}м",
        mins
    )


def get_color(mins):
    if mins <= 0:
        return 0x2ECC71

    if mins > 1440:
        return 0xE74C3C

    if mins > 720:
        return 0xE67E22

    if mins > 360:
        return 0xF1C40F

    return 0x00BFFF


def build_bar(mins):
    max_m = 48 * 60

    ratio = min(
        mins / max_m,
        1
    )

    filled = int(
        (1 - ratio) * 10
    )

    empty = 10 - filled

    if mins <= 0:
        c = "🟩"

    elif mins > 1440:
        c = "🟥"

    elif mins > 720:
        c = "🟧"

    elif mins > 360:
        c = "🟨"

    else:
        c = "🟦"

    return (
        c * filled +
        "⬛" * empty
    )


def format_gil(value):
    return f"{value:,}".replace(",", " ")


def get_custom_emoji(guild, emoji_name):
    if guild is None:
        return ""

    found = discord.utils.get(
        guild.emojis,
        name=emoji_name
    )

    if found:
        return str(found)

    return "▫️"


def item_total(data, item_id):
    count = int(
        data["inventory"].get(item_id, 0)
    )

    price = int(
        ITEMS[item_id]["price"]
    )

    return count * price


def item_block(guild, data, item_id):
    item = ITEMS[item_id]

    emoji = get_custom_emoji(
        guild,
        item["emoji_name"]
    )

    count = int(
        data["inventory"].get(item_id, 0)
    )

    total = item_total(
        data,
        item_id
    )

    return (
        f"{emoji} **{count}**\n"
        f"> {item['title']} • **{format_gil(total)}**"
    )


def group_total(data, group):
    total = 0

    for item_id, item in ITEMS.items():
        if item["group"] != group:
            continue

        total += item_total(
            data,
            item_id
        )

    return total


def get_treasury_status():
    data = load_treasury()
    updated_at = data.get("updated_at")

    if not updated_at:
        return (
            "⚠️ Склад ещё не обновлялся",
            "Нет данных",
            0xF1C40F
        )

    try:
        updated_dt = datetime.fromisoformat(updated_at)
    except:
        return (
            "⚠️ Склад ещё не обновлялся",
            "Нет данных",
            0xF1C40F
        )

    age_hours = (
        now_utc() - updated_dt
    ).total_seconds() / 3600

    local_time = to_andryukha_time(
        updated_dt
    ).strftime("%d.%m • %H:%M")

    if age_hours < 40:
        return (
            "📦 Склад обновлён недавно",
            local_time,
            0x2ECC71
        )

    if age_hours < 72:
        return (
            "⚠️ Склад пора обновить",
            local_time,
            0xF1C40F
        )

    return (
        "🚨 Склад давно не обновлялся",
        local_time,
        0xE74C3C
    )


def build_treasury_embed(guild):
    data = load_treasury()

    gold_blocks = []
    silver_blocks = []

    for kind in ITEM_ORDER:
        gold_blocks.append(
            item_block(
                guild,
                data,
                f"gold_{kind}"
            )
        )

    for kind in ITEM_ORDER:
        silver_blocks.append(
            item_block(
                guild,
                data,
                f"silver_{kind}"
            )
        )

    gold_total = group_total(data, "gold")
    silver_total = group_total(data, "silver")
    total = gold_total + silver_total

    status_text, updated_text, color = get_treasury_status()

    embed = discord.Embed(
        title="📦 Склад FC",
        description="Текущее содержимое сундука компании.",
        color=color
    )

    embed.add_field(
        name="🏅 Золото",
        value=(
            "\n\n".join(gold_blocks) +
            f"\n\n💰 **Итого золото**\n"
            f"**{format_gil(gold_total)}**"
        ),
        inline=False
    )

    embed.add_field(
        name="🥈 Серебро",
        value=(
            "\n\n".join(silver_blocks) +
            f"\n\n💰 **Итого серебро**\n"
            f"**{format_gil(silver_total)}**"
        ),
        inline=False
    )

    embed.add_field(
        name="💎 Общая сумма",
        value=f"**{format_gil(total)} gil**",
        inline=False
    )

    embed.add_field(
        name=status_text,
        value=f"🕒 Последнее обновление: `{updated_text}`",
        inline=False
    )

    return embed


async def refresh_treasury_message(interaction=None, channel=None):
    data = load_treasury()

    target_channel = channel

    if interaction is not None:
        target_channel = interaction.channel

    if target_channel is None:
        return

    embed = build_treasury_embed(
        target_channel.guild
    )

    view = TreasuryView()

    message = None

    if data.get("message_id"):
        try:
            message = await target_channel.fetch_message(
                int(data["message_id"])
            )
        except:
            message = None

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


class GoldModal(ui.Modal):

    def __init__(self):
        super().__init__(
            title="🏅 Обновить золото"
        )

        data = load_treasury()
        inventory = data["inventory"]

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

        except:
            await interaction.response.send_message(
                "Нужно вводить только числа.",
                ephemeral=True
            )
            return

        save_treasury(data)

        await refresh_treasury_message(
            interaction=interaction
        )

        if dashboard_message:
            try:
                await dashboard_message.edit(
                    embeds=build_embeds()
                )
            except Exception as e:
                print("Dashboard update error:", e)

        await interaction.response.send_message(
            "Склад обновлён.",
            ephemeral=True
        )


class SilverModal(ui.Modal):

    def __init__(self):
        super().__init__(
            title="🥈 Обновить серебро"
        )

        data = load_treasury()
        inventory = data["inventory"]

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

        except:
            await interaction.response.send_message(
                "Нужно вводить только числа.",
                ephemeral=True
            )
            return

        save_treasury(data)

        await refresh_treasury_message(
            interaction=interaction
        )

        if dashboard_message:
            try:
                await dashboard_message.edit(
                    embeds=build_embeds()
                )
            except Exception as e:
                print("Dashboard update error:", e)

        await interaction.response.send_message(
            "Склад обновлён.",
            ephemeral=True
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
        style=discord.ButtonStyle.secondary,
        custom_id="treasury_silver"
    )
    async def silver_button(self, interaction, button):
        await interaction.response.send_modal(
            SilverModal()
        )


def build_treasury_status_embed():
    status_text, updated_text, color = get_treasury_status()

    embed = discord.Embed(
        title="📦 Статус склада",
        color=color
    )

    embed.add_field(
        name=status_text,
        value=f"🕒 Последнее обновление: `{updated_text}`",
        inline=False
    )

    return embed


def build_embeds():
    embeds = []

    for i, rt in enumerate(
        return_times,
        1
    ):
        left, mins = format_remaining(rt)

        embed = discord.Embed(
            title=f"🚢 Подлодка #{i}",
            color=get_color(mins)
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
            name="Осталось",
            value=left,
            inline=False
        )

        embed.add_field(
            name="Прогресс",
            value=build_bar(mins),
            inline=False
        )

        embeds.append(embed)

    embeds.append(
        build_treasury_status_embed()
    )

    return embeds


async def send_ready_alert(
    channel,
    index,
    rt
):
    global dashboard_message

    embed = discord.Embed(
        title=(
            f"🚨 ПОДЛОДКА #{index} "
            f"ГОТОВА"
        ),
        color=0x2ECC71
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

    if dashboard_message:
        try:
            embeds = build_embeds()

            await dashboard_message.delete()

            dashboard_message = await channel.send(
                embeds=embeds
            )

        except Exception as e:
            print(e)

    await asyncio.sleep(86400)

    try:
        await msg.delete()
    except:
        pass


async def updater_loop():
    global dashboard_message

    await client.wait_until_ready()

    while not client.is_closed():
        try:
            if dashboard_message:
                await dashboard_message.edit(
                    embeds=build_embeds()
                )

            for i, rt in enumerate(return_times):
                if (
                    not ready_sent[i]
                    and
                    now_utc() >= rt
                ):
                    channel = dashboard_message.channel

                    asyncio.create_task(
                        send_ready_alert(
                            channel,
                            i + 1,
                            rt
                        )
                    )

                    ready_sent[i] = True

        except Exception as e:
            print("Loop error:", e)

        await asyncio.sleep(
            UPDATE_INTERVAL
        )


@client.event
async def on_ready():
    global return_times
    global ready_sent

    print(
        f"Logged as {client.user}"
    )

    client.add_view(
        TreasuryView()
    )

    return_times = load_times()

    ready_sent = (
        [False] * len(return_times)
    )

    print("Bot ready")

    client.loop.create_task(
        updater_loop()
    )


@client.event
async def on_message(message):
    global return_times
    global ready_sent
    global dashboard_message

    if message.author.bot:
        return

    content = message.content.strip().lower()

    if content in ["!treasury", "!склад", "!fc"]:
        await refresh_treasury_message(
            channel=message.channel
        )

        try:
            await message.delete()
        except:
            pass

        return

    if not message.attachments:
        return

    attachment = message.attachments[0]

    if not (
        attachment.filename.endswith(".png")
        or attachment.filename.endswith(".jpg")
        or attachment.filename.endswith(".jpeg")
    ):
        return

    try:
        img_bytes = await attachment.read()

        new_times = parse_image(
            img_bytes
        )

        if len(new_times) != 4:
            return

        return_times = new_times

        ready_sent = (
            [False] * len(return_times)
        )

        save_times(return_times)

        embeds = build_embeds()

        if dashboard_message:
            try:
                await dashboard_message.delete()
            except:
                pass

        dashboard_message = await message.channel.send(
            embeds=embeds
        )

        try:
            await message.delete()
        except:
            pass

        print("Timers updated")

    except Exception as e:
        print(e)


client.run(TOKEN)