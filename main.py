import sqlite3 import random import os import threading import datetime

from aiogram import Bot, Dispatcher, types from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputTextMessageContent, InlineQueryResultArticle from aiogram.utils import executor from fastapi import FastAPI import uvicorn

API_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=API_TOKEN) dp = Dispatcher(bot) app = FastAPI()

conn = sqlite3.connect("database.db", check_same_thread=False) cursor = conn.cursor()

cursor.execute(''' CREATE TABLE IF NOT EXISTS users ( group_id INTEGER, user_id INTEGER, username TEXT, axe_size INTEGER DEFAULT 0, last_growth TEXT, PRIMARY KEY (group_id, user_id) ) ''') conn.commit()

def get_title(axe_size): if axe_size < 20: return "جوجه تبر" elif axe_size < 50: return "تبر تازه‌کار" elif axe_size < 80: return "تبرزن قوی" elif axe_size < 100: return "تبرزن ماهر" else: return "شاه تبر"

def register_user(group_id, user_id, username): cursor.execute("SELECT * FROM users WHERE group_id = ? AND user_id = ?", (group_id, user_id)) if cursor.fetchone() is None: cursor.execute("INSERT INTO users (group_id, user_id, username, axe_size, last_growth) VALUES (?, ?, ?, ?, ?)", (group_id, user_id, username, 0, "")) conn.commit() else: cursor.execute("UPDATE users SET username = ? WHERE group_id = ? AND user_id = ?", (username, group_id, user_id)) conn.commit()

@dp.inline_handler() async def inline_handler(query: types.InlineQuery): user_id = query.from_user.id username = query.from_user.full_name text = query.query.lower().strip() group_id = user_id  # به‌جای chat_id که نداریم، از user_id برای ایزولیشن استفاده می‌کنیم

results = []
now = datetime.datetime.utcnow().date().isoformat()

register_user(group_id, user_id, username)
cursor.execute("SELECT axe_size, last_growth FROM users WHERE group_id = ? AND user_id = ?", (group_id, user_id))
user_data = cursor.fetchone()
axe_size, last_growth = user_data

if not text:
    keyboard = [
        InlineKeyboardButton("🌱 رشد تبر", switch_inline_query_current_chat="رشد"),
        InlineKeyboardButton("🎰 امتحان شانس", switch_inline_query_current_chat="شانس"),
        InlineKeyboardButton("📊 تبرزن‌ها", switch_inline_query_current_chat="تبرزن"),
        InlineKeyboardButton("⚔️ مسابقه تبر (عدد) ✍️", switch_inline_query_current_chat="5 مسابقه تبر")
    ]
    markup = InlineKeyboardMarkup(row_width=2).add(*keyboard)

    results.append(
        InlineQueryResultArticle(
            id="menu",
            title="منوی بازی تبرزن",
            input_message_content=InputTextMessageContent("یکی از گزینه‌ها رو انتخاب کن!"),
            reply_markup=markup
        )
    )

elif "رشد" in text:
    if last_growth == now:
        results.append(
            InlineQueryResultArticle(
                id="already_grew",
                title="🚫 امروز رشد کردی!",
                input_message_content=InputTextMessageContent("تو امروز قبلاً رشد دادی! فردا دوباره بیا.")
            )
        )
    else:
        grow = random.randint(-3, 10)
        new_size = max(0, axe_size + grow)
        cursor.execute("UPDATE users SET axe_size = ?, last_growth = ? WHERE group_id = ? AND user_id = ?",
                       (new_size, now, group_id, user_id))
        conn.commit()
        title = get_title(new_size)

        results.append(
            InlineQueryResultArticle(
                id="growth",
                title="🌱 رشد تبر",
                input_message_content=InputTextMessageContent(
                    f"تبر {username} به اندازه {grow} رشد کرد! الان {new_size} واحده. ({title})")
            )
        )

elif "شانس" in text:
    chance = random.randint(1, 100)
    if chance <= 70:
        new_size = 0
        message = f"💀 بدشانسی! تبر {username} صفر شد!"
    else:
        new_size = axe_size * 2
        message = f"🎉 خوش‌شانسی! تبر {username} دو برابر شد و رسید به {new_size} واحد!"

    cursor.execute("UPDATE users SET axe_size = ? WHERE group_id = ? AND user_id = ?",
                   (new_size, group_id, user_id))
    conn.commit()

    results.append(
        InlineQueryResultArticle(
            id="chance",
            title="🎰 امتحان شانس",
            input_message_content=InputTextMessageContent(message)
        )
    )

elif "تبرزن" in text:
    cursor.execute("SELECT username, axe_size FROM users WHERE group_id = ? ORDER BY axe_size DESC LIMIT 10",
                   (group_id,))
    rows = cursor.fetchall()
    leaderboard = "\n".join(
        [f"{idx + 1}. {row[0]} - {row[1]} ({get_title(row[1])})" for idx, row in enumerate(rows)])

    results.append(
        InlineQueryResultArticle(
            id="leaderboard",
            title="📊 تبرزن‌های برتر",
            input_message_content=InputTextMessageContent(f"🏆 لیست تبرزن‌ها:\n{leaderboard or 'هنوز کسی نیست!'}")
        )
    )

elif "مسابقه تبر" in text:
    parts = text.split()
    if parts[0].isdigit():
        amount = int(parts[0])
        if axe_size < amount:
            results.append(
                InlineQueryResultArticle(
                    id="notenough",
                    title="تبر کافی نداری!",
                    input_message_content=InputTextMessageContent("تبرت برای این مسابقه کافی نیست!")
                )
            )
        else:
            results.append(
                InlineQueryResultArticle(
                    id="duel",
                    title=f"🏹 مسابقه تبر ({amount})",
                    input_message_content=InputTextMessageContent(f"{username} می‌خواد مسابقه بده! برای {amount} واحد!"),
                    reply_markup=InlineKeyboardMarkup().add(
                        InlineKeyboardButton("قبول چالش", callback_data=f"duel|{user_id}|{username}|{amount}")
                    )
                )
            )

await query.answer(results, cache_time=0)

@dp.callback_query_handler(lambda c: c.data.startswith("duel")) async def handle_duel(callback_query: types.CallbackQuery): _, challenger_id, challenger_name, amount = callback_query.data.split("|") challenger_id = int(challenger_id) amount = int(amount) responder = callback_query.from_user

if responder.id == challenger_id:
    await callback_query.answer("نمی‌تونی خودت با خودت مبارزه کنی!", show_alert=True)
    return

# گرفتن اطلاعات از دیتابیس
for uid in (challenger_id, responder.id):
    register_user(uid, uid, responder.full_name if uid == responder.id else challenger_name)

cursor.execute("SELECT axe_size FROM users WHERE group_id = ? AND user_id = ?", (challenger_id, challenger_id))
c_size = cursor.fetchone()[0]
cursor.execute("SELECT axe_size FROM users WHERE group_id = ? AND user_id = ?", (responder.id, responder.id))
r_size = cursor.fetchone()[0]

if c_size < amount or r_size < amount:
    await callback_query.message.edit_text("❌ یکی از طرفین تبر کافی برای این مسابقه نداره!")
    return

winner_id = random.choice([challenger_id, responder.id])
loser_id = responder.id if winner_id == challenger_id else challenger_id

# انتقال امتیاز
cursor.execute("UPDATE users SET axe_size = axe_size + ? WHERE group_id = ? AND user_id = ?",
               (amount, winner_id, winner_id))
cursor.execute("UPDATE users SET axe_size = axe_size - ? WHERE group_id = ? AND user_id = ?",
               (amount, loser_id, loser_id))
conn.commit()

winner = challenger_name if winner_id == challenger_id else responder.full_name
await callback_query.message.edit_text(f"🏆 برنده مسابقه: {winner} ({amount} واحد به دست آورد!)")

@app.get("/") def home(): return {"status": "axe bot is running"}

if name == "main": def start_bot(): executor.start_polling(dp, skip_updates=True)

threading.Thread(target=start_bot).start()
uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))

