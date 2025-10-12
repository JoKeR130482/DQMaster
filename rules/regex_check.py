import re
import pandas as pd

RULE_NAME = "Проверка по регулярному выражению"
RULE_DESC = "Проверяет значение по заданному регулярному выражению. Полезно для сложных проверок формата, например, артикулов или кодов."
IS_CONFIGURABLE = True

PARAMS_SCHEMA = [
    {
        "name": "pattern",
        "type": "text",
        "label": "Регулярное выражение",
        "default": "",
        "required": True
    },
    {
        "name": "mode",
        "type": "select",
        "label": "Режим проверки",
        "default": "matches",
        "options": [
            {"value": "matches", "label": "Ошибка, если НЕ найдено совпадение"},
            {"value": "not_matches", "label": "Ошибка, если найдено совпадение"}
        ]
    }
]

def format_name(params):
    """Форматирует имя правила для отображения в интерфейсе."""
    if not params or not params.get("pattern"):
        return RULE_NAME

    mode = params.get("mode", "matches")
    pattern = params.get("pattern", "")

    mode_text = "не соответствует" if mode == 'matches' else 'соответствует'

    # Усечение длинного паттерна для отображения
    display_pattern = pattern if len(pattern) <= 20 else pattern[:20] + "..."
    return f"Regex '{display_pattern}' ({mode_text})"


def validate(value, params=None):
    """
    Проверяет значение по регулярному выражению.
    - 'matches': ошибка, если совпадение НЕ НАЙДЕНО.
    - 'not_matches': ошибка, если совпадение НАЙДЕНО.
    """
    if pd.isna(value):
        value = "" # Обрабатываем пустые значения как пустые строки

    # Правило применяется только к строкам
    if not isinstance(value, str):
        value = str(value)

    if not params or not params.get("pattern"):
        return True # Не можем выполнить проверку без паттерна

    pattern = params.get("pattern")
    mode = params.get("mode", "matches")

    try:
        # re.search ищет совпадение в любой части строки
        match_found = re.search(pattern, value) is not None
    except re.error as e:
        # Если регулярное выражение некорректно, считаем, что проверка не пройдена,
        # и возвращаем ошибку с деталями.
        # В будущем можно будет показывать эту ошибку пользователю.
        print(f"Invalid regex pattern: {pattern}. Error: {e}")
        return False

    if mode == "matches":
        # ОШИБКА, если совпадение НЕ НАЙДЕНО
        return match_found
    elif mode == "not_matches":
        # ОШИБКА, если совпадение НАЙДЕНО
        return not match_found

    return True