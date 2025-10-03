import re

RULE_NAME = "Проверка на подстроку"
RULE_DESC = "Проверяет, содержит ли значение указанную подстроку или, наоборот, не содержит ее."
IS_CONFIGURABLE = True

def format_name(params):
    """Formats the rule name with its parameters for display."""
    mode = params.get("mode", "contains")
    value = params.get("value", "")
    mode_text = "содержит" if mode == "contains" else "не содержит"
    return f"{RULE_NAME} ({mode_text}: '{value}')"

def validate(value, params=None):
    """
    Checks if a string contains or does not contain a specific substring.
    Non-string values are ignored.
    """
    if not isinstance(value, str):
        return True # This rule only applies to strings.

    if not params:
        # If no params are provided, we can't perform a check.
        # Depending on desired strictness, this could be True or False.
        # Let's consider it True to not throw unnecessary errors.
        return True

    mode = params.get("mode", "contains") # 'contains' or 'not_contains'
    substring = params.get("value", "")

    if not substring:
        # If substring is empty, all strings contain it.
        # This is usually not the desired behavior, so we can treat it as a pass.
        return True

    if mode == "contains":
        return substring in value
    elif mode == "not_contains":
        return substring not in value
    else:
        # Invalid mode, treat as a pass
        return True