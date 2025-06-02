import sqlite3
import random
import os
import threading

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputTextMessageContent, InlineQueryResultArticle
from aiogram.utils import executor

from fastapi import FastAPI
import uvicorn

# خواندن توکن از متغیر محیطی
API_TOKEN = os.getenv('BOT_TOKEN')

# ساخت ربات
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ساخت اپلیکیشن FastAPI
app = FastAPI()

# اتصال به دیتابیس SQLite
conn = sqlite3.connect('database.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    group_id INTEGER,
    user_id INTEGER,
    username TEXT,
    axe_size INTEGER DEFAULT 0,
    PRIMARY KEY (group_id, user_id)
)
''')
conn.commit()

# تابع تعیین لقب بر اساس امتیاز
def get_title(axe_size):
    if axe_size < 20:
        return "جوجه تبر"
    elif axe_size < 50:
        return "تبر تازه‌کار"
    elif axe_size < 80:
        return "تبرزن قوی"
    elif axe_size < 100:
        return "تبرزن ماهر"
    else:
        return "شاه تبر"

# ثبت یا آپدیت کاربر
def register_user(group_id, user_id, username):
    cursor.execute('SELECT * FROM users WHERE group_id = ? AND user_id = ?', (group_id, user_id))
    if cursor.fetchone() is None:
        cursor.execute('INSERT INTO users (group_id, user_id, username, axe_size) VALUES (?, ?, ?, ?)', (group_id, user_id, username, 0))
        conn.commit()
    else:
        cursor.execute('UPDATE users SET username = ? WHERE group_id = ? AND user_id = ?', (username, group_id, user_id))
        conn.commit()

# هندلر اینلاین کوئری
@dp.inline_handler()
async def inline_handler(query: types.InlineQuery):
    user_id = query.from_user.id
    username = query.from_user.full_name
    group_id = query.chat_type

    text = query.query.lower()

    results = []

    if 'رشد' in text:
        grow = random.randint(-3, 10)
        cursor.execute('SELECT axe_size FROM users WHERE group_id = ? AND user_id = ?', (group_id, user_id))
        result = cursor.fetchone()
        if result:
            new_size = result[0] + grow
            if new_size < 0:
                new_size = 0
            cursor.execute('UPDATE users SET axe_size = ? WHERE group_id = ? AND user_id = ?', (new_size, group_id, user_id))
            conn.commit()
        else:
            new_size = max(0, grow)
            register_user(group_id, user_id, username)
            cursor.execute('UPDATE users SET axe_size = ? WHERE group_id = ? AND user_id = ?', (new_size, group_id, user_id))
            conn.commit()
        
        title = get_title(new_size)
        results.append(
            InlineQueryResultArticle(
                id='1',
                title="رشد تبر",
                input_message_content=InputTextMessageContent(
                    f"تبر {username} به اندازه {grow} رشد کرد! الان {new_size} واحد داره. ({title})"
                )
            )
        )

    elif 'شانس' in text:
        cursor.execute('SELECT axe_size FROM users WHERE group_id = ? AND user_id = ?', (group_id, user_id))
        result = cursor.fetchone()
        if not result:
            register_user(group_id, user_id, username)
            cursor.execute('SELECT axe_size FROM users WHERE group_id = ? AND user_id = ?', (group_id, user_id))
            result = cursor.fetchone()

        current_size = result[0]
        chance = random.randint(1, 100)
        if chance <= 70:
            new_size = 0
            message = f"بدشانسی! تبر {username} صفر شد! 😭"
        else:
            new_size = current_size * 2
            message = f"خوش‌شانسی! تبر {username} دو برابر شد و رسید به {new_size} واحد! 😍"

        cursor.execute('UPDATE users SET axe_size = ? WHERE group_id = ? AND user_id = ?', (new_size, group_id, user_id))
        conn.commit()

        results.append(
            InlineQueryResultArticle(
                id='2',
                title="امتحان شانس",
                input_message_content=InputTextMessageContent(message)
            )
        )

    elif 'تبرزن' in text:
        cursor.execute('SELECT username, axe_size FROM users WHERE group_id = ? ORDER BY axe_size DESC LIMIT 10', (group_id,))
        rows = cursor.fetchall()
        if not rows:
            leaderboard = "هیچ تبرزنی هنوز وجود نداره!"
        else:
            leaderboard = ""
            for idx, (user, size) in enumerate(rows, start=1):
                leaderboard += f"{idx}. {user} ({size} واحد - {get_title(size)})\\n"

        results.append(
            InlineQueryResultArticle(
                id='3',
                title="تبرزن‌های برتر",
                input_message_content=InputTextMessageContent(f"🏆 لیست تبرزن‌های برتر:\\n\\n{leaderboard}")
            )
        )

    elif 'تبر زدن' in text:
        parts = text.split()
        if len(parts) < 3:
            results.append(
                InlineQueryResultArticle(
                    id='4',
                    title="خطا",
                    input_message_content=InputTextMessageContent("استفاده درست: تبر زدن به [اسم]")
                )
            )
        else:
            target_name = ' '.join(parts[2:])
            size = random.randint(1, 10)

            keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton(f"تبرش کن! ({size} واحد)", callback_data=f"attack|{user_id}|{username}|{size}")
            )

            results.append(
                InlineQueryResultArticle(
                    id='5',
                    title="حمله تبر",
                    input_message_content=InputTextMessageContent(f"{username} می‌خواهد {target_name} را {size} واحد تبر بزند!"),
                    reply_markup=keyboard
                )
            )

    await query.answer(results, cache_time=0)

# هندلر کلیک دکمه
@dp.callback_query_handler(lambda c: c.data.startswith('attack'))
async def process_callback_attack(callback_query: types.CallbackQuery):
    data = callback_query.data.split('|')
    attacker_id = int(data[1])
    attacker_name = data[2]
    damage = int(data[3])

    if callback_query.from_user.id == attacker_id:
        await callback_query.answer("نمی‌تونی خودتو بزنی!", show_alert=True)
        return

    message = f"🎯 {callback_query.from_user.full_name} {attacker_name} را {damage} واحد تبر زد!"

    await callback_query.message.edit_text(message)

# روت ساده برای زنده نگه داشتن سرور
@app.get("/")
def read_root():
    return {"message": "Axe Bot is Alive!"}

# استارت همزمان ربات و سرور
if __name__ == '__main__':
    def start_bot():
        executor.start_polling(dp, skip_updates=True)

    bot_thread = threading.Thread(target=start_bot)
    bot_thread.start()

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv('PORT', 8080)))
