import os
import asyncio
import logging
import sqlite3
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# --- SOZLAMALAR ---
API_TOKEN = os.getenv('BOT_TOKEN') or "8459649720:AAEr3gOn5cz7NvLE7sdnnIvGSnjAr7ASzLc"
ADMIN_ID = int(os.getenv('ADMIN_ID')) if os.getenv('ADMIN_ID') else 7339714216
MOVIE_CHANNEL_ID = os.getenv('CHANNEL_ID') or "-1002619474183"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- WEBSERVER (Render o'chib qolmasligi uchun) ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is alive!"

def run_webserver():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    thread = Thread(target=run_webserver)
    thread.daemon = True
    thread.start()

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

defaults = [
    ('sub_status', 'on'), ('btn_text', 'Boshqa kino kodlari'), 
    ('btn_url', 'http://t.me/Kino_movie_TMR'), ('app_url', 'https://script.google.com/')
]
for k, v in defaults:
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
db.commit()

# --- FSM STATES ---
class AdminStates(StatesGroup):
    waiting_for_btn_text = State()
    waiting_for_btn_url = State()
    waiting_for_app_url = State()
    waiting_for_ad_text = State()

# --- TUGMALAR ---
def main_admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📢 Reklama yuborish")],
        [KeyboardButton(text="⚙️ Sozlamalar")],
        [KeyboardButton(text="📝 Tugma matni"), KeyboardButton(text="🔗 Tugma linki")],
        [KeyboardButton(text="📱 Ilova linki")]
    ], resize_keyboard=True)

def settings_kb():
    cursor.execute("SELECT value FROM settings WHERE key='sub_status'")
    status = cursor.fetchone()[0]
    sub_text = "🔴 Obuna: O'CHIQ" if status == 'off' else "🟢 Obuna: YOQIQ"
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=sub_text)], [KeyboardButton(text="⬅️ Ortga")]], resize_keyboard=True)

def get_inline_button():
    cursor.execute("SELECT value FROM settings WHERE key='btn_text'"); t = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key='btn_url'"); u = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key='app_url'"); app_url = cursor.fetchone()[0]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, url=u)],
        [InlineKeyboardButton(text="📱 Ilovani ochish", web_app=types.WebAppInfo(url=app_url))]
    ])

# --- STATUS TEKSHIRISH ---
async def get_user_status(user_id: int) -> bool:
    cursor.execute("SELECT value FROM settings WHERE key='sub_status'")
    if cursor.fetchone()[0] == 'off': return True
    try:
        m = await bot.get_chat_member(MOVIE_CHANNEL_ID, user_id)
        return m.status in ['member', 'administrator', 'creator']
    except: return False

# --- HANDLERLAR ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject = None):
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    db.commit()
    args = command.args
    if user_id == ADMIN_ID and not args:
        await message.answer(f"{get_emo('admin')} <b>Admin panel</b>", reply_markup=main_admin_kb(), parse_mode="HTML")
    else:
        if await get_user_status(user_id):
            if args and args.isdigit():
                try: await bot.copy_message(message.chat.id, MOVIE_CHANNEL_ID, int(args), reply_markup=get_inline_button())
                except: await message.answer(f"{get_emo('not_found')} Kino topilmadi!", parse_mode="HTML")
            else: await message.answer(f"{get_emo('welcome')} <b>Xush kelibsiz!</b>\n\nKino kodini yuboring 🎥", parse_mode="HTML")
        else: await message.answer(f"{get_emo('sub')} <b>Kanalga a'zo bo'ling!</b>", reply_markup=get_inline_button(), parse_mode="HTML")

@dp.message(F.text.regexp(r'^\d+$'))
async def search_movie(message: types.Message):
    if not await get_user_status(message.from_user.id):
        await message.answer("Avval a'zo bo'ling!", reply_markup=get_inline_button())
        return
    wait = await message.answer(f"{get_emo('search')} Qidirilmoqda...", parse_mode="HTML")
    try:
        await bot.copy_message(message.chat.id, MOVIE_CHANNEL_ID, int(message.text), reply_markup=get_inline_button())
        await wait.delete()
    except: await wait.edit_text(f"{get_emo('not_found')} Topilmadi!", parse_mode="HTML")

# --- ADMIN FUNKSIYALARI (Siz yuborgan koddagi kabi) ---
@dp.message(F.text == "📊 Statistika", F.from_user.id == ADMIN_ID)
async def stats(m: types.Message):
    cursor.execute("SELECT COUNT(*) FROM users")
    await m.answer(f"📊 Foydalanuvchilar: {cursor.fetchone()[0]}")

@dp.message(F.text == "📢 Reklama yuborish", F.from_user.id == ADMIN_ID)
async def ad_s(m: types.Message, state: FSMContext):
    await m.answer("Reklama xabarini yuboring:")
    await state.set_state(AdminStates.waiting_for_ad_text)

@dp.message(AdminStates.waiting_for_ad_text)
async def ad_f(m: types.Message, state: FSMContext):
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall(); await m.answer("Yuborish boshlandi..."); c = 0
    for u in users:
        try: await m.copy_to(u[0]); c += 1; await asyncio.sleep(0.05)
        except: pass
    await m.answer(f"✅ {c} kishiga yuborildi."); await state.clear()

@dp.message(F.text == "⚙️ Sozlamalar", F.from_user.id == ADMIN_ID)
async def sets(m: types.Message): await m.answer("⚙️ Sozlamalar", reply_markup=settings_kb())

@dp.message(F.text.contains("Obuna:"), F.from_user.id == ADMIN_ID)
async def toggle(m: types.Message):
    cursor.execute("SELECT value FROM settings WHERE key='sub_status'")
    new = 'off' if cursor.fetchone()[0] == 'on' else 'on'
    cursor.execute("UPDATE settings SET value=? WHERE key='sub_status'", (new,))
    db.commit(); await m.answer(f"✅ Status: {new}", reply_markup=settings_kb())

@dp.message(F.text == "⬅️ Ortga", F.from_user.id == ADMIN_ID)
async def back(m: types.Message): await m.answer("Panel", reply_markup=main_admin_kb())

# --- ISHGA TUSHIRISH ---
async def main():
    keep_alive()
    # MUHIM: Polling'dan oldin webhookni o'chirish shart
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
        
