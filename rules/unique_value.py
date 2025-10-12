import pandas as pd

RULE_NAME = "Уникальное значение в столбце"
RULE_DESC = "Проверяет, что значение является уникальным в пределах своего столбца."
IS_CONFIGURABLE = False
NEEDS_COLUMN_ACCESS = True # Флаг, указывающий на то, что правилу нужен весь столбец

def validate(column: pd.Series):
    """
    Проверяет столбец на дубликаты.
    Возвращает pandas Series с булевыми значениями, где True - уникальное, False - дубликат.
    """
    # duplicated() помечает все дубликаты (кроме первого вхождения) как True.
    # keep=False помечает ВСЕ вхождения дубликатов как True.
    # Мы инвертируем результат, чтобы ОШИБКИ (дубликаты) были False.
    return ~column.duplicated(keep=False)