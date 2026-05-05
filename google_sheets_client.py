from __future__ import annotations

import os
from typing import Optional

import gspread
import phonenumbers
from google.oauth2.service_account import Credentials
from phonenumbers import NumberParseException


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _normalize_phone(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None

    try:
        parsed_number = phonenumbers.parse(text, "RU")
    except NumberParseException:
        return None

    if not phonenumbers.is_valid_number(parsed_number):
        return None

    return phonenumbers.format_number(
        parsed_number, phonenumbers.PhoneNumberFormat.E164
    )


class GoogleSheetsClient:
    def __init__(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        service_account_file: str,
    ) -> None:
        creds = Credentials.from_service_account_file(
            service_account_file,
            scopes=SCOPES,
        )
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_key(spreadsheet_id)
        self.worksheet = spreadsheet.worksheet(sheet_name)

    @classmethod
    def from_env(cls) -> "GoogleSheetsClient":
        spreadsheet_id = "1revQXTsZhrO-4ZU8ywMVC4j2MiShpFF-Dq-uk5Gy9Po"
        sheet_name = "Ответы на форму (1)"
        service_account_file = "turslet-bot-590950884fe3.json"


        return cls(
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            service_account_file=service_account_file,
        )

    def find_phone_row_in_column_g(self, phone: str) -> Optional[int]:
        target_phone = _normalize_phone(phone)
        if not target_phone:
            return None

        values = self.worksheet.col_values(7)
        for row_index, raw_value in enumerate(values, start=1):
            candidate_phone = _normalize_phone(raw_value)
            if candidate_phone == target_phone:
                return row_index

        return None


if __name__ == "__main__":
    client = GoogleSheetsClient.from_env()
    test_phone = "+7-985-055-22-00"
    found_row = client.find_phone_row_in_column_g(test_phone)

    if found_row is None:
        print(f"Телефон {test_phone} не найден в колонке G")
    else:
        print(f"Телефон {test_phone} найден в строке {found_row}")
