import re
import pandas as pd

RULE_NAME = "Без специальных символов"
RULE_DESC = "Проверяет, что значение не содержит специальных символов, кроме разрешенных."
IS_CONFIGURABLE = True

PARAMS_SCHEMA = [
    {
        "name": "allowed_chars",
        "type": "text",
        "label": "Дополнительные разрешенные символы",
        "default": "-_."
    }
]

def format_name(params):
    """Форматирует имя правила для отображения в интерфейсе."""
    if not params or not params.get("allowed_chars"):
        return "Без спец. символов"

    allowed = params.get("allowed_chars")
    return f"Без спец. символов (кроме \"{allowed}\")"


def validate(value, params=None):
    """
    Проверяет, что строка содержит только буквы, цифры и разрешенные символы.
    """
    if pd.isna(value):
        return True

    s_value = str(value)
    allowed_chars = params.get("allowed_chars", "-_.") if params else "-_."

    # Создаем регулярное выражение, которое ищет ЛЮБОЙ символ,
    # НЕ являющийся буквой, цифрой или одним из разрешенных.
    # ^ - инверсия
    # \w - любая буква или цифра (эквивалент [a-zA-Z0-9_])
    # re.escape - экранирует символы, чтобы они не интерпретировались как спец. символы regex
    pattern = r'[^a-zA-Zа-яА-ЯёЁ0-9' + re.escape(allowed_chars) + r']'

    # Если поиск находит хотя бы один запрещенный символ, возвращаем False (ошибка)
    if re.search(pattern, s_value):
        return False

    return True