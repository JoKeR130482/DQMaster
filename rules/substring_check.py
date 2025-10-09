import re

RULE_NAME = "Проверка на подстроку"
RULE_DESC = "Проверяет, содержит или не содержит ячейка заданную подстроку. Полезна для поиска стоп-слов или обязательных фрагментов."
IS_CONFIGURABLE = True

# Схема для авто-генерации формы на фронтенде
PARAMS_SCHEMA = [
    {
        "name": "value",
        "type": "text",
        "label": "Подстрока для поиска",
        "default": "",
        "required": True
    },
    {
        "name": "mode",
        "type": "select",
        "label": "Режим проверки",
        "default": "contains",
        "options": [
            {"value": "contains", "label": "Ошибка, если найдено (стоп-слово)"},
            {"value": "not_contains", "label": "Ошибка, если НЕ найдено (обязательная часть)"}
        ]
    },
    {
        "name": "case_sensitive",
        "type": "checkbox",
        "label": "Учитывать регистр",
        "default": False
    }
]

def format_name(params):
    """Форматирует имя правила для отображения в интерфейсе."""
    if not params or not params.get("value"):
        return RULE_NAME # Возвращаем имя по умолчанию, если нет параметров

    mode = params.get("mode", "contains")
    value = params.get("value", "")
    case_sensitive = params.get("case_sensitive", False)

    mode_text = "не содержит" if mode == 'not_contains' else 'содержит'
    case_text = " (регистр важен)" if case_sensitive else ""

    return f"Подстрока '{value}' ({mode_text}{case_text})"

def validate(value, params=None):
    """
    Проверяет наличие или отсутствие подстроки.
    - 'contains': ошибка, если подстрока НАЙДЕНА.
    - 'not_contains': ошибка, если подстрока НЕ НАЙДЕНА.
    """
    # Правило применяется только к строкам
    if not isinstance(value, str):
        return True

    # Если нет параметров или не задана подстрока, не можем выполнить проверку
    if not params or not params.get("value"):
        return True

    substring = params.get("value")
    mode = params.get("mode", "contains")
    case_sensitive = params.get("case_sensitive", False)

    # Приводим строки к нужному регистру для сравнения
    main_string = value if case_sensitive else value.lower()
    search_string = substring if case_sensitive else substring.lower()

    if mode == "contains":
        # ОШИБКА, если подстрока НАЙДЕНА
        return not (search_string in main_string)
    elif mode == "not_contains":
        # ОШИБКА, если подстрока НЕ НАЙДЕНА
        return search_string in main_string

    # Неизвестный режим, считаем, что проверка пройдена
    return True