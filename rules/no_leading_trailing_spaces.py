import pandas as pd

RULE_NAME = "Нет пробелов в начале/конце"
RULE_DESC = "Проверяет, что значение не содержит лишних пробелов в начале или в конце."

def validate(value):
    if not isinstance(value, str):
        return True
    return len(value) == len(value.strip())