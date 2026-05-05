from __future__ import annotations

import asyncio
import os
import re

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from dotenv import load_dotenv


load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing in .env")


class Registration(StatesGroup):
    waiting_phone = State()


dp = Dispatcher(storage=MemoryStorage())


def normalize_phone(text: str) -> str | None:
    digits = re.sub(r"\D", "", text)
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 11 and digits.startswith("7"):
        return f"+{digits}"
    if len(digits) == 10:
        return f"+7{digits}"
    return None


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
            "Можешь, пожалуйста, написать следующим сообщением свой номер телефона "
            "в формате +7 964 532 83 25?\n"
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
            "Не получилось разобрать номер. Пришли, пожалуйста, в формате +7 964 532 83 25 "
            "или 89645328325."
        )
        return
    # здесь: сохранить в БД message.from_user.id -> phone
    await message.answer(f"Принял номер: {phone}. Спасибо!")
    await state.clear()


async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
