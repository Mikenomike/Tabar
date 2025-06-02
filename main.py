import sqlite3
import random
import os
import time
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from fastapi import FastAPI
import uvicorn
import threading

# تنظیمات
API_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
app = FastAPI()

# دیتابیس
conn = sqlite3.connect('database.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    group_id INTEGER,
    user_id INTEGER,
    username TEXT,
    axe_size INTEGER DEFAULT 0,
    last_grow INTEGER DEFAULT 0,
    PRIMARY KEY (group_id, user_id)
)
''')
conn.commit()

# تابع عنوان بر اساس امتیاز
def get_title(size):
    if size < 20:
        return "جوجه تبر"
    elif size < 50:
        return "تبر تازه‌کار"
    elif size < 80:
        return "تبرزن قوی"
    elif size < 100:
        return "تبرزن ماهر"
    else:
        return "شاه تبر"

# ثبت یا آپدیت کاربر
def register_user(group_id, user_id, username):
    cursor.execute('SELECT * FROM users WHERE group_id = ? AND user_id = ?', (group_id, user_id))
    if cursor.fetchone() is None:
        cursor.execute('INSERT INTO users (group_id, user_id, username, axe_size, last_grow) VALUES (?, ?, ?, 0, 0)', (group_id, user_id, username))
        conn.commit()
    else:
        cursor.execute('UPDATE users SET username = ? WHERE group_id = ? AND user_id = ?', (username, group_id, user_id))
        conn.commit()

# inline query
@dp.inline_handler()
async def inline_handler(query: types.InlineQuery):
    user_id = query.from_user.id
    username = query.from_user.full_name
    text = query.query.strip()
    group_id = query.chat_type + str(user_id)  # ایجاد group_id مجازی بر اساس کاربر (زیرا inline کوئری group info نداره)

    results = []

    if not text:
        results.append(
            InlineQueryResultArticle(
                id="grow",
                title="🌱 رشد تبر",
                input_message_content=InputTextMessageContent("رشد"),
                description="افزایش قدرت تبر - فقط یک‌بار در روز"
            )
        )
        results.append(
            InlineQueryResultArticle(
                id="luck",
                title="🎲 امتحان شانس",
                input_message_content=InputTextMessageContent("شانس"),
                description="تبرتو دو برابر کن یا صفرش کن!"
            )
        )
        results.append(
            InlineQueryResultArticle(
                id="top",
                title="🏆 تبرزن‌های برتر",
                input_message_content=InputTextMessageContent("تبرزن"),
                description="نمایش 10 نفر برتر در این گروه"
            )
        )
        results.append(
            InlineQueryResultArticle(
                id="duel",
                title="⚔️ مبارزه تبر",
                input_message_content=InputTextMessageContent("مبارزه 5"),
                description="با یه نفر مسابقه بده و تبر بزن!"
            )
        )

    elif text.startswith("رشد"):
        register_user(group_id, user_id, username)

        cursor.execute('SELECT axe_size, last_grow FROM users WHERE group_id = ? AND user_id = ?', (group_id, user_id))
        row = cursor.fetchone()
        now = int(time.time())

        if now - row[1] < 86400:
            message = "🌱 امروز رشد کردی! فردا دوباره امتحان کن."
        else:
            grow = random.randint(1, 10)
            new_size = row[0] + grow
            cursor.execute('UPDATE users SET axe_size = ?, last_grow = ? WHERE group_id = ? AND user_id = ?', (new_size, now, group_id, user_id))
            conn.commit()
            message = f"🌱 {username} تبرش {grow} واحد رشد کرد! حالا {new_size} واحد داره ({get_title(new_size)})."

        results.append(
            InlineQueryResultArticle(
                id="grow_result",
                title="نتیجه رشد",
                input_message_content=InputTextMessageContent(message)
            )
        )

    elif text.startswith("شانس"):
        register_user(group_id, user_id, username)

        cursor.execute('SELECT axe_size FROM users WHERE group_id = ? AND user_id = ?', (group_id, user_id))
        size = cursor.fetchone()[0]
        chance = random.randint(1, 100)

        if chance <= 70:
            new_size = 0
            message = f"😢 بدشانسی! تبر {username} صفر شد!"
        else:
            new_size = size * 2
            message = f"🎉 خوش‌شانسی! تبر {username} دو برابر شد و شد {new_size} واحد!"

        cursor.execute('UPDATE users SET axe_size = ? WHERE group_id = ? AND user_id = ?', (new_size, group_id, user_id))
        conn.commit()

        results.append(
            InlineQueryResultArticle(
                id="luck_result",
                title="نتیجه شانس",
                input_message_content=InputTextMessageContent(message)
            )
        )

    elif text.startswith("تبرزن"):
        cursor.execute('SELECT username, axe_size FROM users WHERE group_id = ? ORDER BY axe_size DESC LIMIT 10', (group_id,))
        rows = cursor.fetchall()
        leaderboard = "\n".join([f"{i+1}. {name} ({size}) - {get_title(size)}" for i, (name, size) in enumerate(rows)]) or "لیستی وجود ندارد."

        results.append(
            InlineQueryResultArticle(
                id="top_result",
                title="برترین‌ها",
                input_message_content=InputTextMessageContent("🏆 لیست تبرزن‌ها:\n\n" + leaderboard)
            )
        )

    elif text.startswith("مبارزه"):
        parts = text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            results.append(
                InlineQueryResultArticle(
                    id="duel_invalid",
                    title="فرمت اشتباه",
                    input_message_content=InputTextMessageContent("مثال صحیح: مبارزه 5")
                )
            )
        else:
            cost = int(parts[1])
            cursor.execute('SELECT axe_size FROM users WHERE group_id = ? AND user_id = ?', (group_id, user_id))
            row = cursor.fetchone()
            if not row or row[0] < cost:
                results.append(
                    InlineQueryResultArticle(
                        id="duel_fail",
                        title="تبر کافی نداری",
                        input_message_content=InputTextMessageContent("تبر کافی برای مبارزه نداری!")
                    )
                )
            else:
                duel_id = f"{user_id}_{random.randint(1000,9999)}"
                btn = InlineKeyboardMarkup().add(
                    InlineKeyboardButton("قبول مبارزه", callback_data=f"duel|{duel_id}|{user_id}|{cost}|{username}")
                )
                results.append(
                    InlineQueryResultArticle(
                        id="duel_start",
                        title="درخواست مبارزه",
                        input_message_content=InputTextMessageContent(f"⚔️ {username} درخواست مبارزه با {cost} واحد تبر داده!"),
                        reply_markup=btn
                    )
                )

    await query.answer(results, cache_time=0)

# هندلر دکمه مبارزه
@dp.callback_query_handler(lambda c: c.data.startswith("duel"))
async def process_duel(callback: types.CallbackQuery):
    duel_id, attacker_id, cost, attacker_name = callback.data.split('|')[1:]
    attacker_id = int(attacker_id)
    cost = int(cost)
    user_id = callback.from_user.id
    username = callback.from_user.full_name

    if user_id == attacker_id:
        await callback.answer("نمی‌تونی با خودت مبارزه کنی!", show_alert=True)
        return

    group_id = callback.message.chat.id

    cursor.execute('SELECT axe_size FROM users WHERE group_id = ? AND user_id = ?', (group_id, attacker_id))
    attacker = cursor.fetchone()

    cursor.execute('SELECT axe_size FROM users WHERE group_id = ? AND user_id = ?', (group_id, user_id))
    defender = cursor.fetchone()

    if not attacker or attacker[0] < cost:
        await callback.message.edit_text("مبارزه لغو شد! مهاجم تبر کافی نداشت.")
        return

    if not defender or defender[0] < cost:
        await callback.message.edit_text("مبارزه لغو شد! مدافع تبر کافی نداشت.")
        return

    winner = random.choice([attacker_name, username])
    loser = attacker_name if winner == username else username

    # انتقال امتیاز
    if winner == username:
        cursor.execute('UPDATE users SET axe_size = axe_size + ? WHERE group_id = ? AND user_id = ?', (cost, group_id, user_id))
        cursor.execute('UPDATE users SET axe_size = axe_size - ? WHERE group_id = ? AND user_id = ?', (cost, group_id, attacker_id))
    else:
        cursor.execute('UPDATE users SET axe_size = axe_size + ? WHERE group_id = ? AND user_id = ?', (cost, group_id, attacker_id))
        cursor.execute('UPDATE users SET axe_size = axe_size - ? WHERE group_id = ? AND user_id = ?', (cost, group_id, user_id))

    conn.commit()

    await callback.message.edit_text(f"🏆 {winner} در مبارزه برنده شد!\n😢 {loser} بازنده شد و {cost} واحد تبر از دست داد.")

# FastAPI root
@app.get("/")
def read_root():
    return {"status": "ok"}

# اجرای موازی ربات و FastAPI
if __name__ == "__main__":
    def start_bot():
        executor.start_polling(dp, skip_updates=True)

    threading.Thread(target=start_bot).start()
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
