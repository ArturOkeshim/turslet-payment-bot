from __future__ import annotations

from operator import index
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
        self.gender_column = 4
        self.phone_column = 7
        self.chat_id_column = 13
        self.index_column = 16
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

    def find_phone_row_in_column(self, phone: str) -> Optional[int]:
        target_phone = _normalize_phone(phone)
        if not target_phone:
            return None

        values = self.worksheet.col_values(self.phone_column)
        for row_index, raw_value in enumerate(values, start=1):
            candidate_phone = _normalize_phone(raw_value)
            if candidate_phone == target_phone:
                return row_index

        return None
    def index_boys_n_girls(self):
        boys_count = 0
        girls_count = 0
        genders = self.worksheet.col_values(self.gender_column)
        for row_index, raw_value in enumerate(genders, start=1):
            match raw_value.strip():
                case "Мужской":
                    boys_count += 1
                    self.worksheet.update_cell(row_index, self.index_column, boys_count)
                case "Женский":
                    girls_count += 1
                    self.worksheet.update_cell(row_index, self.index_column, girls_count)
                case _:
                    continue        
        return
        
    def save_chat_id_on_telephone(self, target_row: int, chat_id:str):
        self.worksheet.update_cell(target_row, self.chat_id_column, chat_id)


if __name__ == "__main__":

    client = GoogleSheetsClient.from_env()
    client.index_boys_n_girls()