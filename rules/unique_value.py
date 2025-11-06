import pandas as pd
import logging

logger = logging.getLogger(__name__)

RULE_NAME = "Уникальное значение в столбце"
RULE_DESC = "Проверяет, что все значения в столбце являются уникальными. Отмечает все повторяющиеся значения как ошибки."
IS_CONFIGURABLE = False
NEEDS_COLUMN_ACCESS = True # Этот флаг указывает, что правилу нужен доступ ко всему столбцу

def validate(column: pd.Series, params=None):
    """
    Проверяет наличие дубликатов в предоставленном столбце (pandas Series).
    Возвращает словарь с булевой маской Series для валидных строк и списком ошибок.
    """
    try:
        # Проверяем, что на вход подан именно pd.Series
        if not isinstance(column, pd.Series):
            logger.warning(f"Правило 'Уникальное значение' получило неверный тип данных: {type(column)}")
            # Если тип неверный, считаем все значения валидными, чтобы не блокировать процесс
            return {"is_valid": pd.Series([True] * len(column), index=column.index), "errors": None}

        # .duplicated(keep=False) помечает ВСЕ вхождения дубликатов как True
        duplicates_mask = column.duplicated(keep=False)

        # Результат валидации - инвертированная маска (True для уникальных, False для дубликатов)
        is_valid_mask = ~duplicates_mask

        errors = None
        # Если найдены дубликаты, формируем сообщение об ошибке
        if duplicates_mask.any():
            # Находим сами значения-дубликаты, чтобы показать их в сообщении
            duplicate_values = column[duplicates_mask].unique()
            # Ограничиваем количество для читаемости
            display_values = ", ".join(map(str, duplicate_values[:5]))
            if len(duplicate_values) > 5:
                display_values += "..."
            # Это сообщение будет одинаковым для всех строк с дубликатами
            error_message = f"Найдены дубликаты: {display_values}"

            # Создаем Series, где для каждой невалидной строки будет сообщение об ошибке
            errors = pd.Series([error_message if is_dup else None for is_dup in duplicates_mask], index=column.index)

        return {"is_valid": is_valid_mask, "errors": errors}

    except Exception as e:
        logger.error(f"Ошибка при выполнении правила 'Уникальное значение': {e}", exc_info=True)
        # В случае непредвиденной ошибки считаем все значения валидными
        return {"is_valid": pd.Series([True] * len(column), index=column.index), "errors": None}