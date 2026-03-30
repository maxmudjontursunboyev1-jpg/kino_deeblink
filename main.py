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

# --- GLOBAL LOOP ---
main_loop = None

# --- SOZLAMALAR ---
API_TOKEN = os.getenv('BOT_TOKEN') or "8459649720:AAEr3gOn5cz7NvLE7sdnnIvGSnjAr7ASzLc"
ADMIN_ID = int(os.getenv('ADMIN_ID')) if os.getenv('ADMIN_ID') else 7339714216
MOVIE_CHANNEL_ID = os.getenv('CHANNEL_ID') or "-1002619474183"
WEBHOOK_HOST = os.getenv('https://kino-deeblink.onrender.com')
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

# --- TUGMALAR (Sizning kodingizdagidek) ---
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
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=sub_text)],
        [KeyboardButton(text="⬅️ Ortga")]
    ], resize_keyboard=True)

def get_inline_button():
    cursor.execute("SELECT value FROM settings WHERE key='btn_text'"); t = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key='btn_url'"); u = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key='app_url'"); app_url = cursor.fetchone()[0]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, url=u)],
        [InlineKeyboardButton(text="📱 Ilovani ochish", web_app=types.WebAppInfo(url=app_url))]
    ])

# --- OBUNA TEKSHIRISH ---
async def get_user_status(user_id: int) -> bool:
    cursor.execute("SELECT value FROM settings WHERE key='sub_status'")
    if cursor.fetchone()[0] == 'off': return True
    try:
        m = await bot.get_chat_member(MOVIE_CHANNEL_ID, user_id)
        if m.status not in ['member', 'administrator', 'creator']: return False
    except: return False
    return True

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject = None):
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    db.commit()
    
    args = command.args # Deep Linking (Saytdan kelgan kod)
    
    if user_id == ADMIN_ID and not args:
        await message.answer(f"{get_emo('admin')} <b>Admin panel</b>", reply_markup=main_admin_kb(), parse_mode="HTML")
    else:
        if await get_user_status(user_id):
            if args and args.isdigit():
                try:
                    await bot.copy_message(message.chat.id, MOVIE_CHANNEL_ID, int(args), reply_markup=get_inline_button())
                except:
                    await message.answer(f"{get_emo('not_found')} <b>Kino topilmadi!</b>", parse_mode="HTML")
            else:
                await message.answer(f"{get_emo('welcome')} <b>Xush kelibsiz!</b>\n\nKino kodini yuboring 🎥", parse_mode="HTML")
        else:
            await message.answer(f"{get_emo('sub')} <b>Kanalga a'zo bo'ling!</b>", reply_markup=get_inline_button(), parse_mode="HTML")

# --- ADMIN EDIT HANDLERS ---
@dp.message(F.text == "📝 Tugma matni", F.from_user.id == ADMIN_ID)
async def edit_t(message: types.Message, state: FSMContext):
    await message.answer("Yangi tugma matnini yuboring:")
    await state.set_state(AdminStates.waiting_for_btn_text)

@dp.message(F.text == "🔗 Tugma linki", F.from_user.id == ADMIN_ID)
async def edit_u(message: types.Message, state: FSMContext):
    await message.answer("Yangi tugma linkini yuboring:")
    await state.set_state(AdminStates.waiting_for_btn_url)

@dp.message(F.text == "📱 Ilova linki", F.from_user.id == ADMIN_ID)
async def edit_a(message: types.Message, state: FSMContext):
    await message.answer("Yangi Ilova (Apps Script) linkini yuboring:")
    await state.set_state(AdminStates.waiting_for_app_url)

# --- SAVE HANDLERS ---
@dp.message(AdminStates.waiting_for_btn_text)
async def s_t(message: types.Message, state: FSMContext):
    cursor.execute("UPDATE settings SET value=? WHERE key='btn_text'", (message.text,))
    db.commit(); await message.answer("✅ Saqlandi!", reply_markup=main_admin_kb()); await state.clear()

@dp.message(AdminStates.waiting_for_btn_url)
async def s_u(message: types.Message, state: FSMContext):
    if "http" in message.text:
        cursor.execute("UPDATE settings SET value=? WHERE key='btn_url'", (message.text,))
        db.commit(); await message.answer("✅ Saqlandi!", reply_markup=main_admin_kb()); await state.clear()
    else: await message.answer("❌ Xato link!")

@dp.message(AdminStates.waiting_for_app_url)
async def s_a(message: types.Message, state: FSMContext):
    if "http" in message.text:
        cursor.execute("UPDATE settings SET value=? WHERE key='app_url'", (message.text,))
        db.commit(); await message.answer("✅ Saqlandi!", reply_markup=main_admin_kb()); await state.clear()
    else: await message.answer("❌ Xato link!")

# --- KINO SEARCH ---
@dp.message(F.text.regexp(r'^\d+$'))
async def search_movie(message: types.Message):
    if not await get_user_status(message.from_user.id):
        await message.answer(f"{get_emo('sub')} <b>Avval a'zo bo'ling!</b>", reply_markup=get_inline_button(), parse_mode="HTML")
        return
    wait = await message.answer(f"{get_emo('search')} <b>Qidirilmoqda...</b>", parse_mode="HTML")
    try:
        await bot.copy_message(message.chat.id, MOVIE_CHANNEL_ID, int(message.text), reply_markup=get_inline_button())
        await wait.delete()
    except: await wait.edit_text(f"{get_emo('not_found')} <b>Topilmadi!</b>", parse_mode="HTML")

# --- QOLGAN ADMIN FUNKSIYALAR ---
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
async def sets(m: types.Message):
    await m.answer("⚙️ Sozlamalar", reply_markup=settings_kb())

@dp.message(F.text.contains("Obuna:"), F.from_user.id == ADMIN_ID)
async def toggle(m: types.Message):
    cursor.execute("SELECT value FROM settings WHERE key='sub_status'")
    new = 'off' if cursor.fetchone()[0] == 'on' else 'on'
    cursor.execute("UPDATE settings SET value=? WHERE key='sub_status'", (new,))
    db.commit(); await m.answer(f"✅ Status: {new}", reply_markup=settings_kb())

@dp.message(F.text == "⬅️ Ortga", F.from_user.id == ADMIN_ID)
async def back(m: types.Message):
    await m.answer("Asosiy panel", reply_markup=main_admin_kb())

# --- WEBHOOK LOGIKASI ---
@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = Update.model_validate_json(json_string)
        asyncio.run_coroutine_threadsafe(dp.feed_update(bot, update), main_loop)
        return 'OK', 200
    return 'Forbidden', 403

@app.route('/')
def index(): return "Bot is alive and working!", 200

async def on_startup():
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook set to: {WEBHOOK_URL}")

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    main_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(main_loop)
    main_loop.run_until_complete(on_startup())
    app.run(host='0.0.0.0', port=port, debug=False)
