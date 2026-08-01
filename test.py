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

    result = await crypto_request