import asyncio
import logging
import sqlite3
import os
from datetime import datetime, timedelta

import httpx

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==========================================================
# ТОКЕНЫ (вставьте свои значения)
# ==========================================================

BOT_TOKEN = "8277093120:AAGhDiP9iupy51YQRT2LM__23o5-FsbmRJs"

CRYPTOBOT_TOKEN = "59940:AAzmc20qR3Via6BNNq3BBM5sAsfvJzDphh3"


# ==========================================================
# TESTNET CRYPTOBOT
# ==========================================================

CRYPTOBOT_API = "https://testnet-pay.crypt.bot/api"

TEST_PRICE = "1"       # фейковая сумма, ассет тестовый
TEST_DAYS = 30


async def crypto_request(method, data=None):

    headers = {
        "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN
    }

    async with httpx.AsyncClient(timeout=30) as client:

        if data:
            r = await client.post(
                f"{CRYPTOBOT_API}/{method}",
                headers=headers,
                json=data
            )
        else:
            r = await client.get(
                f"{CRYPTOBOT_API}/{method}",
                headers=headers
            )

    result = r.json()

    if not result.get("ok"):
        raise Exception(result)

    return result["result"]


async def create_invoice(user_id):

    invoice = await crypto_request(
        "createInvoice",
        {
            "asset": "USDT",
            "amount": TEST_PRICE,
            "description": "TEST Premium Payment"
        }
    )

    invoice_id = invoice["invoice_id"]

    db_insert_payment(invoice_id, user_id)

    return invoice_id, invoice["pay_url"]


async def check_invoice(invoice_id):

    result = await crypto_request(
        "getInvoices",
        {"invoice_ids": str(invoice_id)}
    )

    items = result.get("items", [])

    if not items:
        return False

    logger.info(f"[TESTNET] invoice {invoice_id} status={items[0]['status']}")

    return items[0]["status"] == "paid"


# ==========================================================
# МИНИМАЛЬНАЯ БАЗА (синхронный sqlite3, файл рядом со скриптом)
# ==========================================================

DB_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "test_payments.db"
)


def db_init():

    conn = sqlite3.connect(DB_FILE)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS payments(
            invoice_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            status TEXT DEFAULT 'created',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()
    conn.close()


def db_insert_payment(invoice_id, user_id):

    conn = sqlite3.connect(DB_FILE)

    conn.execute(
        "INSERT INTO payments (invoice_id, user_id, status) VALUES (?, ?, 'created')",
        (invoice_id, user_id)
    )

    conn.commit()
    conn.close()


def db_get_status(invoice_id):

    conn = sqlite3.connect(DB_FILE)

    cur = conn.execute(
        "SELECT status FROM payments WHERE invoice_id=?",
        (invoice_id,)
    )

    row = cur.fetchone()
    conn.close()

    return row[0] if row else None


def db_mark_paid(invoice_id):

    conn = sqlite3.connect(DB_FILE)

    conn.execute(
        "UPDATE payments SET status='paid' WHERE invoice_id=?",
        (invoice_id,)
    )

    conn.commit()
    conn.close()


# ==========================================================
# BOT
# ==========================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def buy_keyboard():

    kb = InlineKeyboardBuilder()

    kb.row(
        types.InlineKeyboardButton(
            text="🧪 Тестовая покупка",
            callback_data="test:buy"
        )
    )

    return kb.as_markup()


def payment_keyboard(invoice_id, pay_url):

    kb = InlineKeyboardBuilder()

    kb.row(
        types.InlineKeyboardButton(
            text="💎 Оплатить (testnet)",
            url=pay_url
        ),
        types.InlineKeyboardButton(
            text="🔄 Проверить",
            callback_data=f"test:check:{invoice_id}"
        )
    )

    return kb.as_markup()


@dp.message(CommandStart())
async def start_handler(message: types.Message):

    await message.answer(
        "Тестовый бот для проверки оплаты через CryptoBot Testnet.\n\n"
        "Нажмите кнопку ниже, чтобы создать тестовый счёт.",
        reply_markup=buy_keyboard()
    )


@dp.callback_query(F.data == "test:buy")
async def buy_callback(callback: types.CallbackQuery):

    user_id = callback.from_user.id

    try:

        invoice_id, pay_url = await create_invoice(user_id)

    except Exception as e:

        logger.exception(e)

        await callback.message.answer(
            f"Ошибка создания инвойса:\n\n{type(e).__name__}: {e}"
        )

        await callback.answer()

        return

    await callback.message.answer(
        f"Тестовый счёт создан.\n\n"
        f"invoice_id: <code>{invoice_id}</code>\n"
        f"Сумма: {TEST_PRICE} USDT (testnet, фейковая)",
        reply_markup=payment_keyboard(invoice_id, pay_url),
        parse_mode="HTML"
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("test:check:"))
async def check_callback(callback: types.CallbackQuery):

    invoice_id = int(callback.data.split(":")[2])

    status = db_get_status(invoice_id)

    if status == "paid":

        await callback.answer(
            "Этот счёт уже был засчитан ранее (проверка идемпотентности)",
            show_alert=True
        )

        return

    try:

        paid = await check_invoice(invoice_id)

    except Exception as e:

        logger.exception(e)

        await callback.answer(
            f"Ошибка проверки: {type(e).__name__}: {e}",
            show_alert=True
        )

        return

    if not paid:

        await callback.answer(
            "Оплата не найдена. Оплатите счёт по кнопке выше в testnet-боте.",
            show_alert=True
        )

        return

    db_mark_paid(invoice_id)

    expire = datetime.utcnow() + timedelta(days=TEST_DAYS)

    await callback.message.answer(
        f"✅ Оплата подтверждена!\n\n"
        f"invoice_id: <code>{invoice_id}</code>\n"
        f"Тестовый Premium активирован до: <b>{expire.strftime('%d.%m.%Y')}</b>",
        parse_mode="HTML"
    )

    await callback.answer("Оплата подтверждена")


async def main():

    db_init()

    logger.info("Starting TEST payment bot...")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
