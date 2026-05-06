from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from dotenv import load_dotenv

import phonenumbers 
from phonenumbers import NumberParseException
from google_sheets_client import GoogleSheetsClient


load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
RETRY_DELAY_SECONDS = 5

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing in .env")


class Registration(StatesGroup):
    waiting_phone = State()

sheets_client = GoogleSheetsClient.from_env()

dp = Dispatcher(storage=MemoryStorage())


def normalize_phone(text: str) -> str | None:
    try:
        parsed_number = phonenumbers.parse(text, "RU")
    except NumberParseException:
        return None

    if not phonenumbers.is_valid_number(parsed_number):
        return None

    return phonenumbers.format_number(
        parsed_number, phonenumbers.PhoneNumberFormat.E164
    )


@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    check_telephone_to_user_id_link = False  # здесь будем проверять, есть ли у нас этот пользователь в базе.
    if not check_telephone_to_user_id_link:
        first_name = message.from_user.first_name or "участник"
        await message.answer(
            f"{first_name}, привет! Турслет стал больше, и мы решили немного автоматизировать проверку оплат."
        )
        await message.answer(
            "Можешь, пожалуйста, написать следующим сообщением свой номер телефона"
            "в формате +7 999 888 77 66?\n"
            "Это поможет нам точно понять, кто ты из участников."
        )
        await state.set_state(Registration.waiting_phone)
    else:
        await message.answer("Еще раз привет!")


@dp.message(StateFilter(Registration.waiting_phone), F.text)
async def telephone_number_handler(message: Message, state: FSMContext) -> None:
    phone = normalize_phone(message.text.strip())
    if not phone:
        await message.answer(
            "Не получилось разобрать номер."
            "Пришли, пожалуйста, номер текстом в формате +7 999 888 77 66"
        )
        return

    target_row = sheets_client.find_phone_row_in_column(phone)
    if target_row is None:
        await message.answer(
            "Не нашел этот номер в таблице. Проверь формат и номер, "
            "или свяжись с организатором."
        )
        return

    sheets_client.save_chat_id_on_telephone(target_row, str(message.chat.id))
    await message.answer(f"Принял номер: {phone}. Спасибо! Данные обновлены.")
    await state.clear()


async def main() -> None:
    session = AiohttpSession(timeout=30)
    bot = Bot(token=BOT_TOKEN, session=session)
    while True:
        try:
            await dp.start_polling(bot)
            break
        except TelegramNetworkError as error:
            logging.warning(
                "Telegram network error: %s. Retrying in %s seconds...",
                error,
                RETRY_DELAY_SECONDS,
            )
            await asyncio.sleep(RETRY_DELAY_SECONDS)
        except asyncio.TimeoutError:
            logging.warning(
                "Timeout while contacting Telegram API. Retrying in %s seconds...",
                RETRY_DELAY_SECONDS,
            )
            await asyncio.sleep(RETRY_DELAY_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(main())

