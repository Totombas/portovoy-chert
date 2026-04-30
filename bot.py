import io
import json
import re
import os
import asyncio
from datetime import datetime, timedelta

import discord
import pytesseract
from PIL import Image, ImageFilter, ImageOps

TOKEN = os.getenv("DISCORD_TOKEN")

SAVE_FILE = "submarines.json"

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

# =========================================
# TIME
# =========================================

def now_utc():
    return datetime.utcnow()

def to_andryukha_time(dt):
    return dt + timedelta(hours=ANDRYUKHA_OFFSET)

def to_valera_time(dt):
    return dt + timedelta(hours=VALERA_OFFSET)

# =========================================
# JSON
# =========================================

def save_times(times):

    with open(SAVE_FILE, "w") as f:

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
            r'Voyage complete in\s*'
            r'(?:(\d+)d\s*)?'
            r'(?:(\d+)h\s*)?'
            r'(\d+)m',
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

# =========================================
# HELPERS
# =========================================

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

    return embeds

# =========================================
# READY ALERT
# =========================================

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

    # возвращаем dashboard вниз чата
    if dashboard_message:

        try:

            embeds = build_embeds()

            await dashboard_message.delete()

            dashboard_message = await channel.send(
                embeds=embeds
            )

        except Exception as e:

            print(e)

    # удаляем alert через 24 часа
    await asyncio.sleep(86400)

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

# =========================================
# EVENTS
# =========================================

@client.event
async def on_ready():

    global return_times
    global ready_sent

    print(
        f"Logged as {client.user}"
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

            return

        return_times = new_times

        ready_sent = (
            [False] * len(return_times)
        )

        save_times(return_times)

        embeds = build_embeds()

        # удаляем старый dashboard
        if dashboard_message:

            try:

                await dashboard_message.delete()

            except:

                pass

        # создаем новый внизу чата
        dashboard_message = await (
            message.channel.send(
                embeds=embeds
            )
        )

        # удаляем сообщение пользователя
        try:

            await message.delete()

        except:

            pass

        print("Timers updated")

    except Exception as e:

        print(e)

# =========================================
# START
# =========================================

client.run(TOKEN)