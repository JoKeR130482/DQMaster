import re
import pandas as pd

RULE_NAME = "Проверка формата E-mail"
RULE_DESC = "Проверяет, является ли значение валидным E-mail адресом."

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

def validate(value):
    if pd.isna(value) or value == '':
        return True
    if not isinstance(value, str):
        return False
    return EMAIL_REGEX.match(value) is not None