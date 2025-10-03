import re

RULE_NAME = "Проверка на подстроку"
RULE_DESC = "Режим 'содержит (стоп-слово)': ошибка, если подстрока найдена. Режим 'не содержит (обязательно)': ошибка, если подстрока не найдена."
IS_CONFIGURABLE = True

def format_name(params):
    """Formats the rule name with its parameters for display."""
    mode = params.get("mode", "contains")
    value = params.get("value", "")
    case_sensitive = params.get("case_sensitive", False)

    mode_text = "содержит (стоп-слово)" if mode == "contains" else "не содержит (обязательно)"
    case_text = "с учетом регистра" if case_sensitive else "без учета регистра"

    return f"{RULE_NAME} ({mode_text}: '{value}', {case_text})"

def validate(value, params=None):
    """
    Checks for the presence or absence of a substring.
    - 'contains' mode fails if the substring is found.
    - 'not_contains' mode fails if the substring is NOT found.
    """
    if not isinstance(value, str):
        return True # This rule only applies to strings.

    if not params:
        return True # Cannot perform check without params.

    mode = params.get("mode", "contains")
    substring = params.get("value", "")
    case_sensitive = params.get("case_sensitive", False)

    if not substring:
        return True # Cannot check for an empty substring.

    # Prepare strings for comparison based on case sensitivity
    main_string = value if case_sensitive else value.lower()
    search_string = substring if case_sensitive else substring.lower()

    if mode == "contains":
        # It's an ERROR if the substring IS found.
        return not (search_string in main_string)
    elif mode == "not_contains":
        # It's an ERROR if the substring IS NOT found.
        return search_string in main_string

    # Invalid mode, treat as a pass
    return True