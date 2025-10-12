import re
import pandas as pd
from main import app

RULE_NAME = "Проверка формата E-mail"
RULE_DESC = "Проверяет, является ли значение валидным E-mail адресом."

# Простое, но достаточно эффективное регулярное выражение для E-mail
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

def validate(value):
    """
    Ошибка, если строка не соответствует формату E-mail.
    """
    if pd.isna(value) or value == '':
        return True # Пустые значения пропускаем

    if not isinstance(value, str):
        return False # E-mail должен быть строкой

    return EMAIL_REGEX.match(value) is not None