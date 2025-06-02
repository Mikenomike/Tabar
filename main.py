import os
import random
import sqlite3
import asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputTextMessageContent, InlineQueryResultArticle
from aiogram.utils.executor import start_polling

from fastapi import FastAPI
import uvicorn

# توکن از ENV
API_TOKEN = os.getenv('BOT_TOKEN')

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# FastAPI app
app = FastAPI()

# SQLite database
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

# لقب‌ها
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

# ثبت کاربر
def register_user(group_id, user_id, username):
    cursor.execute('SELECT * FROM users WHERE group_id = ? AND user_id = ?', (group_id, user_id))
    if cursor.fetchone() is None:
        cursor.execute('INSERT INTO users (group_id, user_id, username, axe_size) VALUES (?, ?, ?, ?)', (group_id, user_id, username, 0))
        conn.commit()
    else:
        cursor.execute('UPDATE users SET username = ? WHERE group_id = ? AND user_id = ?', (username, group_id, user_id))
        conn.commit()

# هندلر اینلاین
@dp.inline_handler()
async def inline_handler(query: types.InlineQuery):
    user_id = query.from_user.id
    username = query.from_user.full_name
    group_id = user_id  # چون در inline نمی‌تونیم group_id واقعی بگیریم، از user_id به عنوان key موقت استفاده می‌کنیم

    text = query.query.lower()
    results = []

    if 'رشد' in text:
        grow = random.randint(-3, 10)
        cursor.execute('SELECT axe_size FROM users WHERE group_id = ? AND user_id = ?', (group_id, user_id))
        result = cursor.fetchone()
        if result:
            new_size = max(0, result[0] + grow)
            cursor.execute('UPDATE users SET axe_size = ? WHERE group_id = ? AND user_id = ?', (new_size, group_id, user_id))
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
            current_size = 0
        else:
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
        leaderboard = "\n".join(
            f"{idx + 1}. {row[0]} ({row[1]} واحد - {get_title(row[1])})"
            for idx, row in enumerate(rows)
        ) or "هیچ تبرزنی هنوز وجود نداره!"

        results.append(
            InlineQueryResultArticle(
                id='3',
                title="تبرزن‌های برتر",
                input_message_content=InputTextMessageContent(f"🏆 لیست تبرزن‌های برتر:\n\n{leaderboard}")
            )
        )

    await query.answer(results, cache_time=0)

# دکمه‌ها (فعلاً غیرفعال)
@dp.callback_query_handler(lambda c: c.data.startswith('attack'))
async def process_callback_attack(callback_query: types.CallbackQuery):
    await callback_query.answer("حمله تبر هنوز فعال نشده", show_alert=True)

# FastAPI روت تستی
@app.get("/")
def read_root():
    return {"message": "Axe Bot is Alive!"}

# اجرای موازی
async def main():
    config = uvicorn.Config(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
    server = uvicorn.Server(config)

    await asyncio.gather(
        dp.start_polling(),
        server.serve()
    )

if __name__ == '__main__':
    asyncio.run(main())
