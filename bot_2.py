from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from dotenv import load_dotenv

import phonenumbers 
from phonenumbers import NumberParseException
from extract_pdf_text import extract_text_from_pdf
from google_sheets_client import GoogleSheetsClient, RECEIPT_STATUS_SENT


load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
# HTTP: http://host:port или http://user:pass@host:port
# SOCKS: socks5://host:1080 (нужен пакет aiohttp-socks)
TELEGRAM_PROXY = (os.getenv("TELEGRAM_PROXY") or "").strip() or None
RETRY_DELAY_SECONDS = 5

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing in .env")


class Registration(StatesGroup):
    waiting_identity_confirmation = State()
    waiting_phone = State()
    waiting_payment_proof = State()
    all_done = State()

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


async def ask_for_payment_proof(message: Message, state: FSMContext) -> None:
    await state.set_state(Registration.waiting_payment_proof)
    await message.answer(
        "Необходимо оплатить участие в турслете в течение 24 часов с момента регистрации.\n"
        "Переведи 1 рубль на Сбербанк по номеру +7 964 532 83 25 (Артем Мищенко)\n"
        "Для подтверждения пришли в чат чек в виде документа",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    chat_id = str(message.chat.id)
    first_name = message.from_user.first_name or "Участник"

    existing_row = sheets_client.find_row_by_chat_id(chat_id)
    if existing_row is not None:
        if sheets_client.get_conversation_status(existing_row) == RECEIPT_STATUS_SENT:
            await message.answer(
                "Вы уже зарегистрированы, чек мы получили. Если нужна помощь — напиши @artemmish."
            )
            await state.set_state(Registration.all_done)
            return

        await message.answer(f"{first_name}, Вы уже зарегистрированы.")
        await ask_for_payment_proof(message, state)
        return

    await message.answer(
        f"{first_name}, привет! Турслет стал больше, и мы решили немного автоматизировать проверку оплат."
    )

    username = (message.from_user.username or "").strip()
    if username:
        target_row = sheets_client.find_username_row_in_column(username)
        if target_row is not None:
            participant = sheets_client.get_participant_info(target_row)
            full_name = f"{participant['first_name']} {participant['last_name']}".strip()
            display_name = full_name or "участник"
            phone = participant["phone"] or "не указан"
            await state.set_state(Registration.waiting_identity_confirmation)
            await message.answer(
                f"Нашел тебя в списках: {display_name}, телефон: {phone}.\nЭто ты?",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="Да"), KeyboardButton(text="Нет")]],
                    resize_keyboard=True,
                    one_time_keyboard=True,
                ),
            )
            return

    await message.answer(
        "Можешь, пожалуйста, написать следующим сообщением свой номер телефона"
        " в формате +7 XXX XXX XX XX?\n"
        "Это поможет нам точно понять, кто ты из участников."
    )
    await state.set_state(Registration.waiting_phone)


@dp.message(StateFilter(Registration.waiting_identity_confirmation), F.text.casefold() == "да")
async def identity_confirmation_yes_handler(message: Message, state: FSMContext) -> None:
    username = (message.from_user.username or "").strip()
    if not username:
        await message.answer(
            "Не вижу username в Telegram-профиле. Пришлите, пожалуйста, номер телефона в формате +7 XXX XXX XX XX.",
            reply_markup=ReplyKeyboardRemove(),
        )
        await state.set_state(Registration.waiting_phone)
        return

    target_row = sheets_client.find_username_row_in_column(username)
    if target_row is None:
        await message.answer(
            "Не удалось однозначно найти вас по username. Пришлите, пожалуйста, номер телефона в формате +7 XXX XXX XX XX.",
            reply_markup=ReplyKeyboardRemove(),
        )
        await state.set_state(Registration.waiting_phone)
        return

    was_saved = sheets_client.save_chat_id_on_telephone(target_row, str(message.chat.id))
    if not was_saved:
        await message.answer(
            "Этот телефон уже зарегистрирован. Если это точно ваш телефон, напиши @artemmish.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    await message.answer("Отлично, подтвердили личность.", reply_markup=ReplyKeyboardRemove())
    await ask_for_payment_proof(message, state)


@dp.message(StateFilter(Registration.waiting_identity_confirmation), F.text.casefold() == "нет")
async def identity_confirmation_no_handler(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Хорошо, тогда пришли номер телефона в формате +7 XXX XXX XX XX.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(Registration.waiting_phone)


@dp.message(StateFilter(Registration.waiting_identity_confirmation))
async def identity_confirmation_fallback_handler(message: Message) -> None:
    await message.answer("Пожалуйста, выбери один из вариантов: Да или Нет.")


@dp.message(StateFilter(Registration.waiting_phone), F.text)
async def telephone_number_handler(message: Message, state: FSMContext) -> None:
    phone = normalize_phone(message.text.strip())
    if not phone:
        await message.answer(
            "Не получилось разобрать номер."
            "Пришли, пожалуйста, номер текстом в формате +7 XXX XXX XX XX."
        )
        return

    target_row = sheets_client.find_phone_row_in_column(phone)
    if target_row is None:
        await message.answer(
            "Не нашел этот номер среди участников. Проверь формат +7 XXX XXX XX XX  и номер. "
            "Или напиши @artemmish."
        )
        return

    was_saved = sheets_client.save_chat_id_on_telephone(target_row, str(message.chat.id))
    
    if not was_saved:
        await message.answer(
            "Этот телефон уже зарегистрирован. "
            "Если это точно ваш телефон, напиши @artemmish."
        )
        return

    await message.answer(f"Принял номер: {phone}. Спасибо!")
    await ask_for_payment_proof(message, state)

@dp.message(
    StateFilter(Registration.waiting_payment_proof),
    F.document,
    F.document.mime_type == "application/pdf",
)
async def check_handler(message: Message, state: FSMContext) -> None:
    document = message.document
    if document is None:
        await message.answer("Пришлите чек в формате PDF-документа.")
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        pdf_path = Path(temp_dir) / (document.file_name or "payment_check.pdf")
        if pdf_path.suffix.lower() != ".pdf":
            pdf_path = pdf_path.with_suffix(".pdf")

        await message.bot.download(document, destination=pdf_path)

        try:
            extracted_text = extract_text_from_pdf(pdf_path)
        except Exception:
            await message.answer(
                "Не удалось прочитать PDF. Проверь, что это текстовый чек, и отправь файл еще раз."
            )
            return

    if not extracted_text.strip():
        await message.answer(
            "Не нашел текст в чеке. Пришли, пожалуйста, другой PDF (текстовый, не пустой)."
        )
        return

    row_for_chat = sheets_client.find_row_by_chat_id(str(message.chat.id))
    if row_for_chat is not None:
        sheets_client.save_accepted_receipt(row_for_chat, extracted_text)
    else:
        logging.error(
            "PDF accepted but no sheet row for chat_id=%s; status and text not saved",
            message.chat.id,
        )

    await message.answer("Оплата подтверждена, удачного участия в мероприятии!")
    await state.set_state(Registration.all_done)


@dp.message(StateFilter(Registration.waiting_payment_proof))
async def check_handler_fallback(message: Message) -> None:
    await message.answer("Пришли чек в виде PDF-документа (не фото и не текст).")

async def main() -> None:
    session = AiohttpSession(timeout=30, proxy=TELEGRAM_PROXY)
    if TELEGRAM_PROXY:
        logging.info("Using TELEGRAM_PROXY for Bot API requests")
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

@dp.message()
async def polite_answer(message: Message) -> None:
    await message.answer(
        "Отправьте команду /start, чтобы начать пользоваться ботом",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="/start")]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(main())


