from __future__ import annotations

import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv


load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing in .env")

PROXY_URL = (
    os.getenv("PROXY_URL")
    or os.getenv("HTTPS_PROXY")
    or os.getenv("https_proxy")
    or os.getenv("HTTP_PROXY")
    or os.getenv("http_proxy")
)

dp = Dispatcher()


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    await message.answer("Привет! Я бот запущен и готов к работе.")


async def main() -> None:
    session = AiohttpSession(proxy=PROXY_URL) if PROXY_URL else AiohttpSession()
    bot = Bot(token=BOT_TOKEN, session=session)
    try:
        await dp.start_polling(bot)
    except TelegramNetworkError as exc:
        raise RuntimeError(
            "Cannot connect to Telegram API. "
            "If your network uses proxy, set PROXY_URL in .env, "
            "for example: PROXY_URL=http://proxy.server:3128"
        ) from exc


if __name__ == "__main__":
    asyncio.run(main())
