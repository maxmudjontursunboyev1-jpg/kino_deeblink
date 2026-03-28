import os
import asyncio
import logging
import sqlite3
from flask import Flask, request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, Update
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# --- SOZLAMALAR ---
API_TOKEN = os.getenv('BOT_TOKEN') or "8459649720:AAEr3gOn5cz7NvLE7sdnnIvGSnjAr7ASzLc"
ADMIN_ID = int(os.getenv('ADMIN_ID')) if os.getenv('ADMIN_ID') else 7339714216
MOVIE_CHANNEL_ID = os.getenv('CHANNEL_ID') or "-1002619474183"
# Render taqdim etgan URL (masalan: https://loyiha.onrender.com)
WEBHOOK_HOST = os.getenv('RENDER_EXTERNAL_URL') 
WEBHOOK_PATH = f'/webhook/{API_TOKEN}'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# --- LOGGING VA BOT ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
app = Flask(__name__)

# --- PREMIUM EMOJILAR ---
EMOJIS = {
    "welcome": "5199885118214255386", "sub": "5352640560718949874",
    "search": "5458774648621643551", "not_found": "5323329096845897690",
    "admin": "5323772371830588991"
}
def get_emo(name):
    return f'<tg-emoji emoji-id="{EMOJIS.get(name, "✨")}">✨</tg-emoji>'

# --- BAZA BILAN ISHLASH ---
DB_NAME = "bot_data.db"
db = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = db.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS channels (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT UNIQUE)")

# Default sozlamalar
defaults = [('sub_status', 'on'), ('btn_text', 'Boshqa kinolar'), ('btn_url', 'http://t.me/Kino_movie_TMR'), ('app_url', 'https://script.google.com/')]
for k, v in defaults:
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
db.commit()

# --- FSM STATES ---
class AdminStates(StatesGroup):
    waiting_for_btn_text = State()
    waiting_for_btn_url = State()
    waiting_for_ad_text = State()

# --- TUGMALAR ---
def main_admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📢 Reklama")],
        [KeyboardButton(text="⚙️ Sozlamalar")],
        [KeyboardButton(text="📝 Tugma matni"), KeyboardButton(text="🔗 Tugma linki")]
    ], resize_keyboard=True)

def get_inline_button():
    cursor.execute("SELECT value FROM settings WHERE key='btn_text'")
    t = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key='btn_url'")
    u = cursor.fetchone()[0]
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t, url=u)]])

# --- OBUNA TEKSHIRISH ---
async def get_user_status(user_id: int) -> bool:
    cursor.execute("SELECT value FROM settings WHERE key='sub_status'")
    if cursor.fetchone()[0] == 'off': return True
    try:
        m = await bot.get_chat_member(MOVIE_CHANNEL_ID, user_id)
        if m.status not in ['member', 'administrator', 'creator']: return False
    except: return False
    return True

# --- BOT HANDLERLARI ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject = None):
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    db.commit()
    
    args = command.args # Saytdan kelgan kod (?start=123)
    if user_id == ADMIN_ID and not args:
        await message.answer(f"{get_emo('admin')} Admin Panel", reply_markup=main_admin_kb(), parse_mode="HTML")
    else:
        is_sub = await get_user_status(user_id)
        if args and args.isdigit():
            if is_sub:
                try:
                    await bot.copy_message(message.chat.id, MOVIE_CHANNEL_ID, int(args), reply_markup=get_inline_button())
                except:
                    await message.answer(f"{get_emo('not_found')} Topilmadi!", parse_mode="HTML")
            else:
                await message.answer(f"{get_emo('sub')} Obuna bo'ling!", reply_markup=get_inline_button(), parse_mode="HTML")
        else:
            await message.answer(f"{get_emo('welcome')} Kino kodini yuboring!", parse_mode="HTML")

@dp.message(F.text.regexp(r'^\d+$'))
async def search_movie(message: types.Message):
    if not await get_user_status(message.from_user.id):
        await message.answer("Avval obuna bo'ling!", reply_markup=get_inline_button())
        return
    try:
        await bot.copy_message(message.chat.id, MOVIE_CHANNEL_ID, int(message.text), reply_markup=get_inline_button())
    except:
        await message.answer("Kino topilmadi!")

@dp.message(F.text == "📊 Statistika", F.from_user.id == ADMIN_ID)
async def stats(m: types.Message):
    cursor.execute("SELECT COUNT(*) FROM users")
    await m.answer(f"Foydalanuvchilar: {cursor.fetchone()[0]}")

# --- WEBHOOK VA FLASK QISMI ---
@app.route('/')
def index():
    return "<h1>Bot is running with Webhook</h1>", 200

@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = Update.model_validate_json(json_string)
        asyncio.run_coroutine_threadsafe(dp.feed_update(bot, update), asyncio.get_event_loop())
        return '', 200
    else:
        return '', 403

async def on_startup():
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    logging.info(f"Webhook set to: {WEBHOOK_URL}")

if __name__ == "__main__":
    # Webhookni o'rnatish
    loop = asyncio.get_event_loop()
    loop.run_until_complete(on_startup())
    
    # Flask serverni ishga tushirish
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
