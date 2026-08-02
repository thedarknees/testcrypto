import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
import aiosqlite

BOT_TOKEN = "8670653301:AAGr4E132PTO3pU0ZAKD86Tmu9lb92XYQpg"
ADMIN_IDS = [1035443294]
DB_PATH = "/app/data/bot.db"
SCHEMA_PATH = "/app/data/schema.sql"

router = Router()

# ================= ТЕКСТЫ =================

MAIN_TEXT = """📲 Набираем трафферов в команду OF Traffic Insider как с опытом, так и без!

Предоставляем бесплатное обучение и работаем с такими направлениями как:

• Instagram
• TikTok
• Reddit
• YouTube
• X (Twitter)
• Threads

☑️ <b>Плюсы работы с нами:</b>

• Обучение под личным присмотром Тимлида.
• Прозрачная статистика и выплаты каждую пятницу/субботу.
• Фиксированная оплата Free так и Paid подписчиков, либо % по RevShare.
• Новые, конвертирующие модели и регулярно пополняющийся, виральный контент.
• Карьерный рост до Тимлида и выше уже спустя месяц работы.

⚠️ <b>Требования:</b>

• Совершеннолетие (строго 18+)
• Наличие доп. устройства под работу (любой андроид, айфон, помимо личного, либо пк/ноут)
• Свободные 4-6ч в день.

Почитай другие разделы, либо сразу переходи к оформлению заявки в нашу команду из 400+ специалистов ⬇️"""

ABOUT_TEXT = """🧑‍💻 <b>О работе: Траффер. УБТ специалист.</b>

УБТ - это Условно Бесплатный Трафик (другими словами органический).

Основной задачей специалиста в этой сфере, является ведение аккаунтов в соц.сетях и перелив аудитории от туда на страницы моделей.

За каждого такого подписчика (лида) мы платим фиксированную ставку либо % с продаж (Условия выставляются в зависимости от опыта работника и его пожеланий).

⚠️ Важно! Эта работа без фиксированного оклада раз/два в месяц!
Заработок полностью зависит от вашей трудоспособности, готовности к риску и несению ответственности за свои действия.

📲 <b>Чем предстоит заниматься:</b>

• Создавать и вести аккаунты, заливать готовый контент
• Тестировать связки и форматы, находить наиболее конвертирующие креативы
• Масштабировать то, что дает результат.
• Анализировать статистику.

Работа полностью удалённая, график свободный, так что вы сами влияете на результативность, мы помогаем всем чем можем."""

CONDITIONS_TEXT = """💰 <b>Условия и оплата</b>

• Оплата за Free и Paid-подписчиков
• Выплаты раз в неделю
• Прозрачная статистика — видите свои цифры в любой момент
• Новые креативы и модели каждую неделю
• Рост до Team Lead или Owner

<b>Что ждём от Вас:</b>
• готовность работать в потоке и тестировать
• адекватная коммуникация
• желание расти в цифрах

Уже более <b>400+ трафферов</b> работают с нами.

Точные условия обсуждаем индивидуально после заявки."""

FAQ_TEXT = """❗️ <b>FAQ. Частые вопросы:</b>

<b>1. Какой опыт нужен для начала работы?</b>
<blockquote>- Большим преимуществом для вас, будет иметь любой опыт в сфере SMM, арбитраже, но мы так же обучаем ребят с полного 0, опыт не обязателен.</blockquote>

<b>2. Что нужно для старта?</b>
<blockquote>- Зависит от того, какую платформу для работы вы выбираете. Большинство за instagram, так как там самый низкий порог входа, все что нужно это любой айфон или андроид (отдельный от вашего личного устройства), либо пк/ноут</blockquote>

<b>3. Как и когда происходит оплата?</b>
<blockquote>- Оплата считается так: ваша ставка * количество лидов = ваша прибыль. Ставка определяется с каждым лично, отталкиваясь от опыта работы</blockquote>
<blockquote>- Выплаты каждую неделю, по пятницам/субботам</blockquote>

<b>4. Нужен ли бюджет, чтобы начать?</b>
<blockquote>- Только если у вас нет абсолютно никакой техники для работы, в идеале иметь телефон отдельный от личного устройства, так как при работе телефон нужно периодически сбрасывать до заводских настроек</blockquote>
<blockquote>- Для работы с пк/ноута придется оплатить облачный сервис по аренде телефонов, выйдет около 40-60$ в общем</blockquote>"""

# ================= КЛАВИАТУРЫ =================

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧢 О позиции", callback_data="about")],
        [InlineKeyboardButton(text="❓ FAQ", callback_data="faq")],
        [InlineKeyboardButton(text="📝 Оставить заявку", callback_data="apply")],
    ])

def sub_page_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Оставить заявку", callback_data="apply")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")],
    ])

# ================= FSM для анкеты =================
class Form(StatesGroup):
    name = State()
    contact = State()
    experience = State()
    sources = State()

# ================= /start с диплинком =================
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    args = message.text.split(maxsplit=1)
    deeplink_code = args[1] if len(args) > 1 else None
    user_id = message.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        deeplink_id = None
        if deeplink_code:
            cur = await db.execute("SELECT id FROM deeplinks WHERE code=?", (deeplink_code,))
            row = await cur.fetchone()
            if row:
                deeplink_id = row[0]

        cur = await db.execute("SELECT telegram_id FROM users WHERE telegram_id=?", (user_id,))
        existing = await cur.fetchone()
        is_new = existing is None

        if is_new:
            await db.execute(
                "INSERT INTO users (telegram_id, username, source_deeplink_id) VALUES (?,?,?)",
                (user_id, message.from_user.username, deeplink_id)
            )
        if deeplink_id:
            await db.execute(
                "INSERT INTO clicks (deeplink_id, user_id, is_new_user) VALUES (?,?,?)",
                (deeplink_id, user_id, is_new)
            )
        await db.commit()

    await message.answer(MAIN_TEXT, reply_markup=main_menu_kb())

# ================= Разделы меню =================
@router.callback_query(F.data == "about")
async def show_about(call: CallbackQuery):
    await call.message.edit_text(ABOUT_TEXT, reply_markup=sub_page_kb())

@router.callback_query(F.data == "faq")
async def show_faq(call: CallbackQuery):
    await call.message.edit_text(FAQ_TEXT, reply_markup=sub_page_kb())

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(MAIN_TEXT, reply_markup=main_menu_kb())

# ================= Анкета =================
@router.callback_query(F.data == "apply")
async def start_application(call: CallbackQuery, state: FSMContext):
    await state.set_state(Form.name)
    await call.message.edit_text("Как вас зовут? Напишите имя (или ник):")

@router.message(Form.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Form.contact)
    await message.answer("Оставьте контакт для связи (ваш @username в Telegram или номер телефона):")

@router.message(Form.contact)
async def get_contact(message: Message, state: FSMContext):
    await state.update_data(contact=message.text)
    await state.set_state(Form.experience)
    await message.answer("Есть ли опыт в трафике/баинге? Если да — кратко опишите:")

@router.message(Form.experience)
async def get_experience(message: Message, state: FSMContext):
    await state.update_data(experience=message.text)
    await state.set_state(Form.sources)
    await message.answer("С какими источниками готовы работать? (TikTok, Instagram, Threads, X, YouTube, Reddit — можно несколько):")

@router.message(Form.sources)
async def get_sources(message: Message, state: FSMContext):
    data = await state.update_data(sources=message.text)
    user_id = message.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT source_deeplink_id FROM users WHERE telegram_id=?", (user_id,))
        row = await cur.fetchone()
        deeplink_id = row[0] if row else None

        await db.execute(
            """INSERT INTO applications 
               (user_id, deeplink_id, full_name, phone, age, city, comment) 
               VALUES (?,?,?,?,?,?,?)""",
            (user_id, deeplink_id, data['name'], data['contact'], None, None, 
             f"Опыт: {data['experience']}\nИсточники: {data['sources']}")
        )
        await db.commit()

    await state.clear()
    await message.answer(
        "Спасибо! Заявка принята ✅\nМы свяжемся с вами в ближайшее время.",
        reply_markup=main_menu_kb()
    )

    bot: Bot = message.bot
    for admin_id in ADMIN_IDS:
        await bot.send_message(
            admin_id,
            f"🆕 <b>Новая заявка</b>\n\n"
            f"Имя: {data['name']}\n"
            f"Контакт: {data['contact']}\n"
            f"Опыт: {data['experience']}\n"
            f"Источники: {data['sources']}\n"
            f"User ID: <code>{user_id}</code>\n"
            f"Username: @{message.from_user.username or '-'}"
        )

# ================= АДМИНКА =================
@router.message(Command("newlink"))
async def create_deeplink(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Использование: /newlink код Название кампании")
        return
    code, name = args[1], args[2]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO deeplinks (code, name, created_by) VALUES (?,?,?)",
            (code, name, message.from_user.id)
        )
        await db.commit()

    bot_username = (await message.bot.get_me()).username
    await message.answer(f"Диплинк создан:\nhttps://t.me/{bot_username}?start={code}")

@router.message(Command("stats"))
async def show_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT d.name, d.code,
                   COUNT(DISTINCT c.id) as clicks,
                   COUNT(DISTINCT CASE WHEN c.is_new_user THEN c.user_id END) as new_users,
                   COUNT(DISTINCT a.id) as applications
            FROM deeplinks d
            LEFT JOIN clicks c ON c.deeplink_id = d.id
            LEFT JOIN applications a ON a.deeplink_id = d.id
            GROUP BY d.id
            ORDER BY clicks DESC
        """)
        rows = await cur.fetchall()

    if not rows:
        await message.answer("Пока нет данных.")
        return

    text = "📊 <b>Статистика по источникам:</b>\n\n"
    for name, code, clicks, new_users, apps in rows:
        conv = f"{(apps/clicks*100):.1f}%" if clicks else "0%"
        text += (
            f"🔹 <b>{name}</b> (<code>{code}</code>)\n"
            f"Переходов: {clicks} | Новых: {new_users}\n"
            f"Заявок: {apps} | Конверсия: {conv}\n\n"
        )
    await message.answer(text)

@router.message(Command("links"))
async def list_links(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    bot_username = (await message.bot.get_me()).username
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT code, name FROM deeplinks ORDER BY id DESC")
        rows = await cur.fetchall()
    if not rows:
        await message.answer("Диплинков пока нет.")
        return
    text = "🔗 <b>Активные диплинки:</b>\n\n"
    for code, name in rows:
        text += f"{name}\nhttps://t.me/{bot_username}?start={code}\n\n"
    await message.answer(text)

# ================= Инициализация БД =================
async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            await db.executescript(f.read())
        await db.commit()

async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())