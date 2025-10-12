import pandas as pd

RULE_NAME = "Нет пробелов в начале/конце"
RULE_DESC = "Проверяет, что значение не содержит лишних пробелов в начале или в конце."

def validate(value):
    """
    Ошибка, если у строки есть пробелы в начале или в конце.
    """
    if not isinstance(value, str):
        return True # Правило применяется только к строкам

    # Если длина строки не изменилась после strip(), значит, пробелов не было
    return len(value) == len(value.strip())