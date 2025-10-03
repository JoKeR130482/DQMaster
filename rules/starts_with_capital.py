import re

RULE_NAME = "Не начинается с заглавной"
RULE_DESC = "Ошибка, если значение является строкой и не начинается с заглавной буквы."

def validate(value):
    """
    Checks if a value is a string that does NOT start with a capital letter.
    Non-string values are ignored (not considered invalid).
    An empty string is considered an error.
    """
    # This rule only applies to strings.
    if not isinstance(value, str):
        return True # Not an error for this rule if the cell is empty, a number, etc.

    # If it's an empty string, it's an error.
    if not value:
        return False

    # Regex for Cyrillic or Latin capital letter at the beginning of the string
    pattern = r'^[A-ZА-Я]'
    return re.match(pattern, value) is not None