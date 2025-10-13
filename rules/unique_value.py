import pandas as pd

RULE_NAME = "Уникальное значение в столбце"
RULE_DESC = "Проверяет, что значение является уникальным в пределах своего столбца."
IS_CONFIGURABLE = False
NEEDS_COLUMN_ACCESS = True

def validate(column: pd.Series):
    return ~column.duplicated(keep=False)