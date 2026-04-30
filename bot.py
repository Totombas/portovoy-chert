import io
import json
import re
import asyncio
from datetime import datetime, timedelta

import discord
import pytesseract
import requests

from PIL import (
    Image,
    ImageFilter,
    ImageOps
)

# =========================================
# НАСТРОЙКИ
# =========================================

TOKEN = "PASTE_TOKEN_LATER"

CHANNEL_NAME = "подлодки"

SAVE_FILE = "submarines.json"

UPDATE_INTERVAL = 15

USER_IDS = [
    "259731173918507010",  # totomba
    "293071176631189504",  # darianvein
]

pytesseract.pytesseract.tesseract_cmd = (
    r"/usr/bin/tesseract"
)

# =========================================
# DISCORD
# =========================================

intents = discord.Intents.default()

intents.message_content = True

client = discord.Client(
    intents=intents
)

dashboard_message = None

return_times = []

ready_sent = []

# =========================================
# JSON
# =========================================

def save_times(times):

    with open(
        SAVE_FILE,
        "w"
    ) as f:

        json.dump(
            [x.isoformat() for x in times],
            f
        )

def load_times():

    try:

        with open(SAVE_FILE) as f:

            return [
                datetime.fromisoformat(x)
                for x in json.load(f)
            ]

    except:

        return []

# =========================================
# OCR
# =========================================

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

    text = pytesseract.image_to_string(img)

    text = (
        text
        .replace("Om", "0m")
        .replace("Oh", "0h")
        .replace("Id", "1d")
        .replace("Ih", "1h")
    )

    lines = [

        l

        for l in text.splitlines()

        if "Voyage complete in" in l
    ]

    result = []

    for line in lines[:4]:

        m = re.search(
            r'(?:(\d+)d)?\s*'
            r'(?:(\d+)h)?\s*'
            r'(\d+)m',
            line
        )

        if not m:
            continue

        d = int(m.group(1) or 0)

        h = int(m.group(2) or 0)

        m_ = int(m.group(3))

        total = (
            d * 1440 +
            h * 60 +
            m_
        )

        result.append(
            datetime.now() +
            timedelta(minutes=total)
        )

    return result

# =========================================
# HELPERS
# =========================================

def get_ping_text():

    return " ".join(
        f"<@{i}>"
        for i in USER_IDS
    )

def format_remaining(rt):

    delta = rt - datetime.now()

    if delta.total_seconds() <= 0:

        return "ГОТОВО ✅", 0

    mins = int(
        delta.total_seconds() // 60
    )

    d = mins // 1440

    h = (
        (mins % 1440) // 60
    )

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

# =========================================
# EMBEDS
# =========================================

def build_embeds():

    embeds = []

    for i, rt in enumerate(
        return_times,
        1
    ):

        left, mins = (
            format_remaining(rt)
        )

        embed = discord.Embed(

            title=(
                f"🚢 Подлодка #{i}"
            ),

            color=get_color(mins)
        )

        embed.add_field(
            name="Андрюха",
            value=rt.strftime("%H:%M"),
            inline=True
        )

        embed.add_field(
            name="Валера",
            value=(
                rt +
                timedelta(hours=2)
            ).strftime("%H:%M"),
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

    now = datetime.now()

    upd = discord.Embed(
        title="🕒 Обновлено",
        color=0x95A5A6
    )

    upd.add_field(
        name="Андрюха",
        value=now.strftime("%H:%M:%S"),
        inline=True
    )

    upd.add_field(
        name="Валера",
        value=(
            now +
            timedelta(hours=2)
        ).strftime("%H:%M:%S"),
        inline=True
    )

    embeds.append(upd)

    return embeds

# =========================================
# READY ALERT
# =========================================

async def send_ready_alert(
    channel,
    index,
    rt
):

    embed = discord.Embed(

        title=(
            f"🚨 ПОДЛОДКА #{index} "
            f"ГОТОВА"
        ),

        color=0x2ECC71
    )

    embed.add_field(
        name="Андрюха",
        value=rt.strftime("%H:%M"),
        inline=True
    )

    embed.add_field(
        name="Валера",
        value=(
            rt +
            timedelta(hours=2)
        ).strftime("%H:%M"),
        inline=True
    )

    embed.add_field(
        name="Статус",
        value="ВОЗВРАЩАЙ ЛОДКУ 🚢",
        inline=False
    )

    msg = await channel.send(
        get_ping_text(),
        embed=embed
    )

    await asyncio.sleep(600)

    try:
        await msg.delete()
    except:
        pass

# =========================================
# LOOP
# =========================================

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
                    datetime.now() >= rt
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

# =========================================
# EVENTS
# =========================================

@client.event
async def on_ready():

    global return_times
    global ready_sent
    global dashboard_message

    print(
        f"Logged as {client.user}"
    )

    return_times = load_times()

    ready_sent = (
        [False] * len(return_times)
    )

    for guild in client.guilds:

        for channel in guild.text_channels:

            if (
                channel.name ==
                CHANNEL_NAME
            ):

                dashboard_message = (
                    await channel.send(
                        embeds=build_embeds()
                    )
                )

                print(
                    "Dashboard created"
                )

    client.loop.create_task(
        updater_loop()
    )

@client.event
async def on_message(message):

    global return_times
    global ready_sent

    if message.author.bot:
        return

    if not message.attachments:
        return

    attachment = (
        message.attachments[0]
    )

    if not (
        attachment.filename.endswith(".png")
        or
        attachment.filename.endswith(".jpg")
        or
        attachment.filename.endswith(".jpeg")
    ):
        return

    try:

        img_bytes = await (
            attachment.read()
        )

        new_times = parse_image(
            img_bytes
        )

        if len(new_times) != 4:

            await message.reply(
                (
                    "❌ OCR не смог "
                    "найти 4 лодки"
                )
            )

            return

        return_times = new_times

        ready_sent = (
            [False] * len(return_times)
        )

        save_times(return_times)

        await message.reply(
            "🚢 Таймеры обновлены"
        )

        print("Timers updated")

    except Exception as e:

        print(e)

        await message.reply(
            f"❌ Ошибка OCR: {e}"
        )

# =========================================
# START
# =========================================

client.run(TOKEN)