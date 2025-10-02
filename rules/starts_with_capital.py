import re

RULE_NAME = "Начинается с заглавной"
RULE_DESC = "Проверяет, что значение является строкой и начинается с заглавной буквы (кириллица или латиница)."

def validate(value):
    """
    Checks if a string starts with a capital letter (Cyrillic or Latin).
    Returns True if valid, False otherwise.
    """
    if not isinstance(value, str):
        return False

    # Regex for Cyrillic or Latin capital letter at the beginning of the string
    pattern = r'^[A-ZА-Я]'
    return re.match(pattern, value) is not None