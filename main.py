import asyncio
import logging
import random
import os
import sqlite3
import time
from pathlib import Path
from contextlib import closing

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "xizcl").lstrip("@")
DB = "goldway.db"
BANNER = Path(__file__).parent / "assets" / "goldway-menu-banner.png"
PROFILE_BANNER = Path(__file__).parent / "assets" / "goldway-profile-banner.png"
PRODUCT_BANNER = Path(__file__).parent / "assets" / "goldway-catalog-banner.png"
RULES_BANNER = Path(__file__).parent / "assets" / "goldway-rules-banner.png"
FAQ_BANNER = Path(__file__).parent / "assets" / "goldway-faq-banner.png"
CAPTCHAS = {}
LAST_ORDER_TIME = {}
ORDER_STATUSES = {"new": "🆕 Новый", "paid": "💳 Оплачен", "processing": "⚙️ Выполняется", "ready": "✅ Готов", "cancelled": "❌ Отменён"}
router = Router()

TEXT = {
    "ru": {"welcome": "Добро пожаловать в магазин Goldway 🛍\n\nВыберите раздел:", "products": "🛍 Товары", "profile": "👤 Профиль", "support": "💬 Поддержка", "rules": "📜 Правила / Соглашение", "faq": "❓ FAQ", "empty": "Товары пока не добавлены.", "contact": "Для покупки свяжитесь с администратором: @{admin}", "back": "↩️ Назад", "admin": "⚙️ Админ-панель"},
    "en": {"welcome": "Welcome to Goldway store 🛍\n\nChoose a section:", "products": "🛍 Products", "profile": "👤 Profile", "support": "💬 Support", "rules": "📜 Rules / Agreement", "faq": "❓ FAQ", "empty": "No products have been added yet.", "contact": "To purchase, contact the administrator: @{admin}", "back": "↩️ Back", "admin": "⚙️ Admin panel"},
}

FAQ = {
    "ru": """❓ FAQ — Частые вопросы

📌 ОБЩИЕ ВОПРОСЫ

🤖 Что делает этот бот?
Бот помогает пополнять баланс внутриигровой валюты и покупать игровые предметы для мобильных игр.

🛡 Это безопасно?
Да. Мы используем проверенные платёжные каналы, не передаём данные третьим лицам и фиксируем транзакции.

🎮 Какие игры поддерживаются?
Список игр находится в меню бота. Если нужной игры нет — напишите в поддержку.

💳 ПОПОЛНЕНИЕ И ОПЛАТА

🛒 Как пополнить баланс?
1️⃣ Выберите игру.
2️⃣ Укажите игровой ID или никнейм.
3️⃣ Выберите сумму или пакет валюты.
4️⃣ Оплатите удобным способом.
5️⃣ Дождитесь подтверждения и зачисления.

⏱ Сколько времени занимает зачисление?
Обычно от 2 до 15 минут. В редких случаях — до 24 часов.

🧾 Что делать, если валюта не пришла?
Сохраните чек и напишите в поддержку, указав игровой ID.

🎁 ДОНАТ И ПАКЕТЫ

🏷 Есть ли скидки или бонусы?
Да, в боте регулярно проходят акции и действуют бонусы за первое пополнение.

💎 Можно ли купить конкретный предмет?
Да, если он есть в каталоге. Иначе можно пополнить валюту и купить предмет в игре.

💰 Почему цена отличается от официальной?
Цена зависит от комиссии платёжных систем, курса валют и особенностей пополнения.

🆘 ПОДДЕРЖКА И ПРОБЛЕМЫ

📞 Куда писать, если что-то не работает?
В поддержку внутри бота или администратору @xizcl. Укажите игровой ID, сумму, дату и способ оплаты.

↩️ Можно ли вернуть деньги?
Возврат возможен до отправки валюты в игру при ошибке с нашей стороны. После зачисления возврат не производится.

⚠️ Что делать, если я ошибся в игровом ID?
Сразу напишите в поддержку. Если валюта ещё не зачислена, мы постараемся помочь.""",
    "en": """❓ FAQ — Frequently Asked Questions

📌 GENERAL QUESTIONS

🤖 What does this bot do?
The bot helps top up in-game currency and buy game items for mobile games.

🛡 Is it safe?
Yes. We use verified payment channels, do not share user data with third parties, and record transactions.

🎮 Which games are supported?
The supported games are listed in the bot menu. If your game is missing, contact support.

💳 TOP-UP AND PAYMENT

🛒 How do I top up?
1️⃣ Choose a game. 2️⃣ Enter your game ID or nickname. 3️⃣ Choose a package. 4️⃣ Pay. 5️⃣ Wait for confirmation.

⏱ How long does it take?
Usually 2–15 minutes. In rare cases, up to 24 hours.

🧾 What if the currency does not arrive?
Save your receipt and contact support with your game ID.

🎁 DONATIONS AND PACKAGES

🏷 Are discounts or bonuses available?
Yes, promotions and first-top-up bonuses are offered regularly.

💎 Can I buy a specific item?
Yes, if it is available in the catalog. Otherwise, top up currency and buy it in-game.

🆘 SUPPORT AND ISSUES

📞 Contact support in the bot or message @xizcl. Include your game ID, amount, date, and payment method.

↩️ Refunds are possible before delivery if the error is on our side. After delivery, refunds are unavailable.

⚠️ Entered the wrong game ID?
Contact support immediately. We will try to help if the currency has not been delivered.""",
}

RULES = {
    "ru": """📜 ПРАВИЛА / ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ

1️⃣ ТЕРМИНЫ
🤖 Бот — сервис Telegram для заказа внутриигровой валюты и предметов.
👤 Пользователь — лицо, использующее Бот.
🛍 Услуга — организация пополнения баланса или передачи предметов.
🎮 Игровой аккаунт — аккаунт, идентифицируемый по ID/никнейму.
💳 Платёж — перевод средств через платёжные системы.

2️⃣ ПРЕДМЕТ СОГЛАШЕНИЯ
Бот позволяет заказать пополнение игровой валюты или получение предметов. Услуга оказывается привлечёнными поставщиками. Использование Бота и оплата заказа означают принятие настоящего Соглашения.

3️⃣ ПОРЯДОК ОКАЗАНИЯ УСЛУГИ
🔹 Пользователь выбирает игру, указывает ID/никнейм, пакет и способ оплаты.
🔹 После подтверждения заказа и оплаты оператор передаёт его поставщику.
🔹 Зачисление выполняется поставщиком на стороне игры.
⏱ Срок: обычно 2–15 минут, в отдельных случаях — до 24 часов.

4️⃣ ОПЛАТА И ВОЗВРАТ
💰 Цена учитывает комиссии платёжных систем, курс валют и условия поставщиков.
✅ Платёж считается завершённым после подтверждения системой.
↩️ Возврат возможен до отправки валюты при ошибке со стороны Бота/поставщика. После зачисления возврат не производится.

5️⃣ ОБЯЗАННОСТИ
👤 Пользователь обязан указывать достоверный ID/никнейм, не использовать Бот для мошенничества или обхода правил игры и не передавать данные заказа третьим лицам.
🛠 Оператор обеспечивает работу Бота, передаёт заказы поставщикам и оказывает поддержку.

6️⃣ ОГРАНИЧЕНИЕ ОТВЕТСТВЕННОСТИ
Оператор не отвечает за сбои игровой платформы, санкции игры в отношении аккаунта и ошибки из-за неверного ID/никнейма. Мгновенное зачисление не гарантируется. Оператор не является правообладателем игр и не выдаёт лицензии на игровой контент.

7️⃣ ДАННЫЕ И БЕЗОПАСНОСТЬ
Для заказа могут обрабатываться игровой ID и данные платежа в зашифрованном виде. Данные используются по политике конфиденциальности и могут храниться для поддержки и разрешения споров.

8️⃣ ИЗМЕНЕНИЯ И ПРИОСТАНОВКА
Оператор может обновлять Соглашение публикацией новой редакции. Продолжение использования Бота означает согласие с изменениями. Услуги могут быть временно приостановлены при технических работах, нарушениях или по требованию платёжных систем.

9️⃣ ПРОЧИЕ УСЛОВИЯ
Споры решаются переговорами, а при отсутствии согласия — по законодательству страны регистрации оператора. Коммерческое использование Бота без согласования запрещено.""",
    "en": """📜 RULES / USER AGREEMENT

🤖 The Bot is a Telegram service for ordering in-game currency and items. The User accepts this Agreement by using the Bot or paying for an order.

🛍 The User selects a game, enters a valid game ID/nickname, chooses a package and payment method. After payment confirmation, the order is sent to a third-party supplier. Delivery usually takes 2–15 minutes, and in exceptional cases up to 24 hours.

💰 Prices include payment-system fees, exchange rates and supplier terms. Refunds are possible only before delivery if the error is on our side. After delivery, refunds are unavailable.

👤 The User must provide accurate data and must not use the Bot for fraud, illegal actions or bypassing game rules. The Operator provides support and forwards orders within a reasonable time.

⚠️ The Operator is not responsible for game-platform failures, game sanctions or an incorrect ID/nickname. Instant delivery is not guaranteed. The Operator is not the game copyright holder.

🔐 Order data may be stored as needed for support and dispute resolution under the Bot privacy policy. The Agreement may be updated by publishing a new version. Disputes are governed by the law of the Operator's country of registration.""",
}

def db_init():
    with closing(sqlite3.connect(DB)) as c:
        c.execute("CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, name_ru TEXT NOT NULL, name_en TEXT NOT NULL, game TEXT DEFAULT 'Общие', description_ru TEXT, description_en TEXT, price TEXT NOT NULL, active INTEGER DEFAULT 1)")
        columns = [row[1] for row in c.execute("PRAGMA table_info(products)").fetchall()]
        if "game" not in columns: c.execute("ALTER TABLE products ADD COLUMN game TEXT DEFAULT 'Общие'")
        c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, language TEXT DEFAULT 'ru')")
        c.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, username TEXT, game TEXT NOT NULL, product_id INTEGER, product_name TEXT NOT NULL, price TEXT NOT NULL, game_id TEXT NOT NULL, nickname TEXT NOT NULL, status TEXT DEFAULT 'new', created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        c.commit()

def lang(user_id):
    with closing(sqlite3.connect(DB)) as c:
        row = c.execute("SELECT language FROM users WHERE id=?", (user_id,)).fetchone()
    return row[0] if row else "ru"

def set_lang(user_id, value):
    with closing(sqlite3.connect(DB)) as c:
        c.execute("INSERT INTO users(id, language) VALUES(?, ?) ON CONFLICT(id) DO UPDATE SET language=excluded.language", (user_id, value)); c.commit()

def menu(l):
    t = TEXT[l]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["products"], callback_data="products"), InlineKeyboardButton(text=t["profile"], callback_data="profile")],
        [InlineKeyboardButton(text=t["support"], url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton(text="🌐 Language / Язык", callback_data="language")],
        [InlineKeyboardButton(text=t["rules"], callback_data="rules"), InlineKeyboardButton(text=t["faq"], callback_data="faq")],
    ])

def back(l): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=TEXT[l]["back"], callback_data="home")]])

async def replace(c, text, reply_markup):
    await c.message.delete()
    await c.message.answer(text, reply_markup=reply_markup)

@router.message(CommandStart())
async def start(m: Message):
    l = lang(m.from_user.id); set_lang(m.from_user.id, l)
    a, b = random.randint(2, 9), random.randint(2, 9)
    answer = a + b; CAPTCHAS[m.from_user.id] = answer
    options = {answer, answer + 1, answer - 1}
    kb = [[InlineKeyboardButton(text=str(x), callback_data=f"captcha:{x}") for x in options]]
    prompt = (f"🛡 Проверка безопасности\n\nРешите пример, чтобы открыть магазин:\n\n🔢 Сколько будет {a} + {b}?" if l == 'ru' else f"🛡 Security check\n\nSolve this problem to open the store:\n\n🔢 What is {a} + {b}?")
    await m.answer(prompt, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    return

@router.callback_query(F.data.startswith("captcha:"))
async def captcha_check(c: CallbackQuery):
    l = lang(c.from_user.id); expected = CAPTCHAS.get(c.from_user.id)
    if expected is None or int(c.data.split(":", 1)[1]) != expected:
        await c.answer("❌ Неверный ответ, попробуйте ещё раз." if l == 'ru' else "❌ Wrong answer, try again.", show_alert=True); return
    CAPTCHAS.pop(c.from_user.id, None); await c.message.delete()
    if BANNER.exists():
        await c.message.answer_photo(FSInputFile(BANNER), caption=TEXT[l]["welcome"], reply_markup=menu(l))
    else:
        await c.message.answer(TEXT[l]["welcome"], reply_markup=menu(l))
    await c.answer()

@router.callback_query(F.data == "home")
async def home(c: CallbackQuery):
    l=lang(c.from_user.id); await c.message.delete()
    if BANNER.exists(): await c.message.answer_photo(FSInputFile(BANNER), caption=TEXT[l]["welcome"], reply_markup=menu(l))
    else: await c.message.answer(TEXT[l]["welcome"], reply_markup=menu(l))
    await c.answer()

@router.callback_query(F.data == "language")
async def language(c: CallbackQuery):
    await replace(c, "Выберите язык / Choose language:", InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang:ru"), InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang:en")], [InlineKeyboardButton(text="↩️", callback_data="home")]])); await c.answer()

@router.callback_query(F.data.startswith("setlang:"))
async def set_language(c: CallbackQuery):
    set_lang(c.from_user.id, c.data.split(":")[1]); await replace(c, TEXT[lang(c.from_user.id)]["welcome"], menu(lang(c.from_user.id))); await c.answer()

@router.callback_query(F.data == "products")
async def products(c: CallbackQuery):
    l=lang(c.from_user.id)
    with closing(sqlite3.connect(DB)) as con: games=con.execute("SELECT DISTINCT game FROM products WHERE active=1 ORDER BY game").fetchall()
    if not games: await replace(c, TEXT[l]["empty"], back(l)); return
    kb=[[InlineKeyboardButton(text=f"🎮 {g[0]}", callback_data=f"game:{g[0]}")] for g in games]
    kb.append([InlineKeyboardButton(text=TEXT[l]["back"], callback_data="home")]); markup=InlineKeyboardMarkup(inline_keyboard=kb)
    await c.message.delete()
    if PRODUCT_BANNER.exists(): await c.message.answer_photo(FSInputFile(PRODUCT_BANNER), caption="🎮 Выберите игру:" if l=='ru' else "🎮 Choose a game:", reply_markup=markup)
    else: await c.message.answer("🎮 Выберите игру:" if l=='ru' else "🎮 Choose a game:", reply_markup=markup)
    await c.answer()

@router.callback_query(F.data.startswith("game:"))
async def game_products(c: CallbackQuery):
    l=lang(c.from_user.id); game=c.data.split(":",1)[1]
    with closing(sqlite3.connect(DB)) as con: rows=con.execute("SELECT id,name_ru,name_en,price FROM products WHERE active=1 AND game=?", (game,)).fetchall()
    kb=[[InlineKeyboardButton(text=f"💎 {r[1] if l=='ru' else r[2]} — {r[3]}", callback_data=f"product:{r[0]}")] for r in rows]
    kb.append([InlineKeyboardButton(text="↩️ Игры" if l=='ru' else "↩️ Games", callback_data="products")]); await replace(c, f"🛍 {game}\n\n" + ("Выберите товар:" if l=='ru' else "Choose a product:"), InlineKeyboardMarkup(inline_keyboard=kb)); await c.answer()

class OrderForm(StatesGroup):
    game_id=State(); nickname=State()

@router.callback_query(F.data.startswith("product:"))
async def product_detail(c: CallbackQuery, state: FSMContext):
    l=lang(c.from_user.id); product_id=int(c.data.split(":",1)[1])
    with closing(sqlite3.connect(DB)) as con: row=con.execute("SELECT id,game,name_ru,name_en,price FROM products WHERE id=? AND active=1", (product_id,)).fetchone()
    if not row: await c.answer("Товар недоступен", show_alert=True); return
    name=row[2] if l=='ru' else row[3]
    await state.update_data(product_id=row[0], game=row[1], product_name=name, price=row[4])
    await replace(c, f"🛍 {name}\n🎮 Игра: {row[1]}\n💰 Цена: {row[4]}\n\nВведите игровой ID:", InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_order")]])); await state.set_state(OrderForm.game_id); await c.answer()

@router.message(OrderForm.game_id)
async def order_game_id(m: Message, state: FSMContext):
    await state.update_data(game_id=m.text.strip()); await state.set_state(OrderForm.nickname); await m.answer("Введите игровой никнейм:")

@router.message(OrderForm.nickname)
async def order_nickname(m: Message, state: FSMContext):
    d=await state.update_data(nickname=m.text.strip()); l=lang(m.from_user.id)
    await m.answer(f"📋 Проверьте заказ:\n\n🎮 Игра: {d['game']}\n🛍 Товар: {d['product_name']}\n🆔 Игровой ID: {d['game_id']}\n👤 Никнейм: {d['nickname']}\n💰 Цена: {d['price']}\n\nПодтвердить заказ?" if l=='ru' else f"📋 Check your order:\n\n🎮 Game: {d['game']}\n🛍 Product: {d['product_name']}\n🆔 Game ID: {d['game_id']}\n👤 Nickname: {d['nickname']}\n💰 Price: {d['price']}\n\nConfirm order?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Подтвердить" if l=='ru' else "✅ Confirm", callback_data="confirm_order"), InlineKeyboardButton(text="❌ Отмена" if l=='ru' else "❌ Cancel", callback_data="cancel_order")]]))

@router.callback_query(F.data == "cancel_order")
async def cancel_order(c: CallbackQuery, state: FSMContext):
    await state.clear(); await c.message.delete(); await c.message.answer("Заказ отменён. Вернитесь в каталог через /start."); await c.answer()

@router.callback_query(F.data == "confirm_order")
async def confirm_order(c: CallbackQuery, state: FSMContext):
    d=await state.get_data(); user_id=c.from_user.id; now=time.time()
    if now - LAST_ORDER_TIME.get(user_id, 0) < 30: await c.answer("Подождите 30 секунд перед новым заказом.", show_alert=True); return
    with closing(sqlite3.connect(DB)) as con:
        duplicate=con.execute("SELECT id FROM orders WHERE user_id=? AND product_id=? AND game_id=? AND nickname=? AND status IN ('new','paid','processing') AND created_at >= datetime('now','-10 minutes')", (user_id,d['product_id'],d['game_id'],d['nickname'])).fetchone()
        if duplicate: await c.answer("Такой заказ уже ожидает обработки.", show_alert=True); return
        cur=con.execute("INSERT INTO orders(user_id,username,game,product_id,product_name,price,game_id,nickname) VALUES(?,?,?,?,?,?,?,?)", (user_id,c.from_user.username or '',d['game'],d['product_id'],d['product_name'],d['price'],d['game_id'],d['nickname'])); order_id=cur.lastrowid; con.commit()
    LAST_ORDER_TIME[user_id]=now; await state.clear(); await c.message.delete(); await c.message.answer(f"✅ Заказ #{order_id} создан!\n\nОжидайте связи с администратором @{ADMIN_USERNAME} для оплаты и выполнения заказа.")
    admin_text=f"🆕 НОВЫЙ ЗАКАЗ #{order_id}\n\n👤 Пользователь: @{c.from_user.username or 'без username'} ({user_id})\n🎮 Игра: {d['game']}\n🛍 Товар: {d['product_name']}\n🆔 Игровой ID: {d['game_id']}\n🔗 Никнейм: {d['nickname']}\n💰 Цена: {d['price']}"
    status_kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💳 Оплачен", callback_data=f"status:{order_id}:paid"), InlineKeyboardButton(text="⚙️ Выполняется", callback_data=f"status:{order_id}:processing")],[InlineKeyboardButton(text="✅ Готов", callback_data=f"status:{order_id}:ready"), InlineKeyboardButton(text="❌ Отменён", callback_data=f"status:{order_id}:cancelled")]])
    for admin_id in ADMIN_IDS:
        try: await c.bot.send_message(admin_id, admin_text, reply_markup=status_kb)
        except Exception: logging.exception("Admin notification failed")

@router.callback_query(F.data == "profile")
async def profile(c: CallbackQuery):
    l=lang(c.from_user.id); user=c.from_user
    name=(user.full_name or "Пользователь").replace("<", "").replace(">", "")
    username=f"@{user.username}" if user.username else "не указан" if l=='ru' else "not set"
    with closing(sqlite3.connect(DB)) as con:
        count=con.execute("SELECT COUNT(*) FROM orders WHERE user_id=?", (user.id,)).fetchone()[0]
        history=con.execute("SELECT id,product_name,status FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 5", (user.id,)).fetchall()
    history_text="\n".join(f"• #{o[0]} — {o[1]} — {ORDER_STATUSES.get(o[2], o[2])}" for o in history) or ("Пока нет заказов." if l=='ru' else "No orders yet.")
    text=(f"👤 ПРОФИЛЬ GOLDWAY\n\n🪪 Имя: {name}\n🔗 Username: {username}\n🆔 Telegram ID: {user.id}\n📦 Всего заказов: {count}\n\n📜 ИСТОРИЯ ПОКУПОК\n{history_text}\n\n🛍 Выберите товар в каталоге или обратитесь в поддержку." if l=='ru' else f"👤 GOLDWAY PROFILE\n\n🪪 Name: {name}\n🔗 Username: {username}\n🆔 Telegram ID: {user.id}\n📦 Total orders: {count}\n\n📜 PURCHASE HISTORY\n{history_text}\n\n🛍 Choose a product or contact support.")
    await c.message.delete()
    if PROFILE_BANNER.exists():
        await c.message.answer_photo(FSInputFile(PROFILE_BANNER), caption="👤 ПРОФИЛЬ GOLDWAY" if l=='ru' else "👤 GOLDWAY PROFILE")
        await c.message.answer(text, reply_markup=back(l))
    else: await c.message.answer(text, reply_markup=back(l))
    await c.answer()

@router.callback_query(F.data.in_({"rules","faq"}))
async def info(c: CallbackQuery):
    l=lang(c.from_user.id); key=c.data
    body={"rules": RULES[l], "faq": FAQ[l]}[key]
    banner={"rules": RULES_BANNER, "faq": FAQ_BANNER}[key]
    await c.message.delete()
    if banner.exists():
        await c.message.answer_photo(FSInputFile(banner), caption="📜 Правила / Соглашение" if key == "rules" and l == 'ru' else "❓ FAQ" if l == 'ru' else "📜 Rules / Agreement" if key == "rules" else "❓ FAQ")
        await c.message.answer(body, reply_markup=back(l))
    else: await c.message.answer(body, reply_markup=back(l))
    await c.answer()

class AddProduct(StatesGroup):
    game=State(); name_ru=State(); name_en=State(); price=State()

class EditProduct(StatesGroup):
    data=State()

def is_admin(m): return m.from_user.id in ADMIN_IDS

def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin:add")],[InlineKeyboardButton(text="🛍 Управление товарами", callback_data="admin:products")],[InlineKeyboardButton(text="📋 Заказы", callback_data="admin:orders")]])

async def show_admin(c):
    await replace(c, "⚙️ АДМИН-ПАНЕЛЬ\n\nВыберите действие:", admin_keyboard())

@router.message(Command("admin"))
async def admin(m: Message):
    if not is_admin(m): return
    await m.answer("⚙️ АДМИН-ПАНЕЛЬ\n\nВыберите действие:", reply_markup=admin_keyboard())

@router.callback_query(F.data == "admin:panel")
async def admin_panel(c: CallbackQuery):
    if c.from_user.id not in ADMIN_IDS: return
    await show_admin(c); await c.answer()

@router.callback_query(F.data == "admin:add")
async def admin_add(c: CallbackQuery, state: FSMContext):
    if c.from_user.id not in ADMIN_IDS: return
    await state.set_state(AddProduct.game); await c.message.answer("➕ Введите название игры:"); await c.answer()

@router.message(Command("add"))
async def add(m: Message, state: FSMContext):
    if not is_admin(m): return
    await state.set_state(AddProduct.game); await m.answer("Введите название игры:")

@router.message(AddProduct.game)
async def add_game(m: Message, state: FSMContext): await state.update_data(game=m.text.strip()); await state.set_state(AddProduct.name_ru); await m.answer("Введите название товара на русском:")

@router.message(AddProduct.name_ru)
async def add_ru(m: Message, state: FSMContext): await state.update_data(name_ru=m.text.strip()); await state.set_state(AddProduct.name_en); await m.answer("Введите название товара на английском:")
@router.message(AddProduct.name_en)
async def add_en(m: Message, state: FSMContext): await state.update_data(name_en=m.text.strip()); await state.set_state(AddProduct.price); await m.answer("Введите цену текстом, например 100 ₽:")
@router.message(AddProduct.price)
async def add_price(m: Message, state: FSMContext):
    d=await state.update_data(price=m.text.strip())
    with closing(sqlite3.connect(DB)) as c: c.execute("INSERT INTO products(game,name_ru,name_en,price) VALUES(?,?,?,?)", (d['game'],d['name_ru'],d['name_en'],d['price'])); c.commit()
    await state.clear(); await m.answer("Товар добавлен ✅", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⚙️ В админ-панель", callback_data="admin:panel")]]))

@router.callback_query(F.data == "admin:products")
async def admin_products(c: CallbackQuery):
    if c.from_user.id not in ADMIN_IDS: return
    with closing(sqlite3.connect(DB)) as con: rows=con.execute("SELECT id,game,name_ru,price FROM products WHERE active=1 ORDER BY game,id").fetchall()
    if not rows: await replace(c, "🛍 Товаров пока нет.", InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Добавить", callback_data="admin:add")],[InlineKeyboardButton(text="↩️ Назад", callback_data="admin:panel")]])); await c.answer(); return
    kb=[]
    for row in rows:
        kb.append([InlineKeyboardButton(text=f"{row[1]} • {row[2]} • {row[3]}", callback_data=f"admin:edit:{row[0]}"), InlineKeyboardButton(text="🗑", callback_data=f"admin:delete:{row[0]}")])
    kb.append([InlineKeyboardButton(text="➕ Добавить", callback_data="admin:add")]); kb.append([InlineKeyboardButton(text="↩️ Назад", callback_data="admin:panel")]); await replace(c, "🛍 УПРАВЛЕНИЕ ТОВАРАМИ\n\nНажмите на товар для редактирования:", InlineKeyboardMarkup(inline_keyboard=kb)); await c.answer()

@router.callback_query(F.data.startswith("admin:delete:"))
async def admin_delete(c: CallbackQuery):
    if c.from_user.id not in ADMIN_IDS: return
    product_id=int(c.data.rsplit(":",1)[1])
    with closing(sqlite3.connect(DB)) as con: con.execute("UPDATE products SET active=0 WHERE id=?", (product_id,)); con.commit()
    await c.answer("Товар удалён ✅"); await admin_products(c)

@router.callback_query(F.data.startswith("admin:edit:"))
async def admin_edit(c: CallbackQuery, state: FSMContext):
    if c.from_user.id not in ADMIN_IDS: return
    product_id=int(c.data.rsplit(":",1)[1]); await state.update_data(product_id=product_id); await state.set_state(EditProduct.data)
    await c.message.answer("✏️ Отправьте данные одной строкой через |\n\nИгра | Название RU | Название EN | Цена\n\nНапример:\nBrawl Stars | 500 гемов | 500 gems | 399 ₽"); await c.answer()

@router.message(EditProduct.data)
async def edit_product(m: Message, state: FSMContext):
    d=await state.get_data(); parts=[x.strip() for x in (m.text or '').split('|')]
    if len(parts) != 4: await m.answer("Нужно 4 поля через символ |. Попробуйте ещё раз."); return
    with closing(sqlite3.connect(DB)) as con: con.execute("UPDATE products SET game=?,name_ru=?,name_en=?,price=?,active=1 WHERE id=?", (*parts,d['product_id'])); con.commit()
    await state.clear(); await m.answer("Товар обновлён ✅", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛍 К товарам", callback_data="admin:products")]]))

@router.callback_query(F.data == "admin:orders")
async def admin_orders(c: CallbackQuery):
    if c.from_user.id not in ADMIN_IDS: return
    with closing(sqlite3.connect(DB)) as con: rows=con.execute("SELECT id,game,product_name,status FROM orders ORDER BY id DESC LIMIT 20").fetchall()
    if not rows: text="📋 Заказов пока нет."; kb=[[InlineKeyboardButton(text="↩️ Назад", callback_data="admin:panel")]]
    else:
        text="📋 ЗАКАЗЫ\n\nВыберите заказ:"; kb=[[InlineKeyboardButton(text=f"#{r[0]} • {r[1]} • {ORDER_STATUSES.get(r[3],r[3])}", callback_data=f"admin:order:{r[0]}")] for r in rows]; kb.append([InlineKeyboardButton(text="↩️ Назад", callback_data="admin:panel")])
    await replace(c, text, InlineKeyboardMarkup(inline_keyboard=kb)); await c.answer()

@router.callback_query(F.data.startswith("admin:order:"))
async def admin_order(c: CallbackQuery):
    if c.from_user.id not in ADMIN_IDS: return
    order_id=int(c.data.rsplit(":",1)[1])
    with closing(sqlite3.connect(DB)) as con: r=con.execute("SELECT id,user_id,username,game,product_name,price,game_id,nickname,status,created_at FROM orders WHERE id=?", (order_id,)).fetchone()
    if not r: await c.answer("Заказ не найден", show_alert=True); return
    text=f"📋 ЗАКАЗ #{r[0]}\n\n👤 @{r[2] or 'без username'} ({r[1]})\n🎮 Игра: {r[3]}\n🛍 Товар: {r[4]}\n💰 Цена: {r[5]}\n🆔 Игровой ID: {r[6]}\n🔗 Никнейм: {r[7]}\n📌 Статус: {ORDER_STATUSES.get(r[8],r[8])}\n🕒 {r[9]}"
    kb=[[InlineKeyboardButton(text="🆕 Новый", callback_data=f"status:{order_id}:new"),InlineKeyboardButton(text="💳 Оплачен", callback_data=f"status:{order_id}:paid")],[InlineKeyboardButton(text="⚙️ Выполняется", callback_data=f"status:{order_id}:processing"),InlineKeyboardButton(text="✅ Готов", callback_data=f"status:{order_id}:ready")],[InlineKeyboardButton(text="❌ Отменён", callback_data=f"status:{order_id}:cancelled")],[InlineKeyboardButton(text="↩️ Заказы", callback_data="admin:orders")]]
    await replace(c,text,InlineKeyboardMarkup(inline_keyboard=kb)); await c.answer()

@router.callback_query(F.data.startswith("status:"))
async def change_status(c: CallbackQuery):
    if c.from_user.id not in ADMIN_IDS: return
    _,order_id,status=c.data.split(":"); order_id=int(order_id)
    with closing(sqlite3.connect(DB)) as con: row=con.execute("SELECT user_id FROM orders WHERE id=?", (order_id,)).fetchone(); con.execute("UPDATE orders SET status=? WHERE id=?", (status,order_id)); con.commit()
    if not row: await c.answer("Заказ не найден", show_alert=True); return
    await c.bot.send_message(row[0], f"📌 Статус заказа #{order_id}: {ORDER_STATUSES[status]}")
    await c.answer("Статус обновлён ✅"); await admin_order(c)

async def main():
    if not TOKEN or TOKEN == "PASTE_NEW_TOKEN_HERE": raise RuntimeError("Укажите новый BOT_TOKEN в .env")
    db_init(); bot=Bot(TOKEN); dp=Dispatcher(); dp.include_router(router); await dp.start_polling(bot)

if __name__ == "__main__": logging.basicConfig(level=logging.INFO); asyncio.run(main())
