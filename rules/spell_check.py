# Заменить текущую реализацию на более надежную
import re
import pandas as pd
import logging
from spellchecker import SpellChecker

logger = logging.getLogger("dqmaster")

RULE_NAME = "Проверка орфографии"
RULE_DESC = "Проверяет правильность написания слов на русском языке с учетом контекста"
NEEDS_COLUMN_ACCESS = True
IS_CASE_SENSITIVE = False
IS_CONFIGURABLE = True
PARAMS_SCHEMA = [
    {
        "name": "min_word_length",
        "type": "number",
        "label": "Минимальная длина слова для проверки",
        "default": 4,
        "min": 2,
        "max": 10
    },
    {
        "name": "custom_dictionary",
        "type": "text",
        "label": "Дополнительные слова (через запятую)",
        "placeholder": "термин1, термин2, термин3"
    },
    {
        "name": "ignore_capitalized",
        "type": "checkbox",
        "label": "Игнорировать слова с заглавной буквы",
        "default": True
    }
]

def init_spell_checker(params=None):
    """Инициализирует проверщик орфографии с настройками"""
    spell = SpellChecker(language='ru', case_sensitive=False)

    # Добавление пользовательских слов в словарь
    custom_words = []
    if params and params.get("custom_dictionary"):
        custom_words = [word.strip().lower() for word in params["custom_dictionary"].split(",") if word.strip()]
        spell.word_frequency.load_words(custom_words)
        logger.debug(f"Загружено {len(custom_words)} пользовательских слов в словарь орфографии")

    return spell, custom_words

def validate_column(column, params=None):
    """Проверяет орфографию для всего столбца сразу"""
    if params is None:
        params = {}

    min_word_length = params.get("min_word_length", 4)
    ignore_capitalized = params.get("ignore_capitalized", True)

    spell, custom_words = init_spell_checker(params)
    errors = []
    rows_with_errors = 0

    for idx, value in enumerate(column):
        if pd.isna(value) or str(value).strip() == "":
            continue

        text = str(value)
        words = re.findall(r'\b[а-яА-ЯёЁa-zA-Z]+\b', text)

        misspelled_words = []
        for word in words:
            if len(word) < min_word_length:
                continue

            # Пропускаем слова с заглавной буквы в начале предложения
            if ignore_capitalized and word[0].isupper() and idx > 0:
                continue

            # Пропускаем пользовательские слова
            if word.lower() in custom_words:
                continue

            if word.lower() not in spell:
                misspelled_words.append(word)

        if misspelled_words:
            rows_with_errors += 1
            error_msg = f"Орфографические ошибки: {', '.join(misspelled_words)}"
            errors.append({
                'row': idx + 2,  # +2 потому что в Excel нумерация с 1, плюс заголовок
                'value': text,
                'error': error_msg
            })

    is_valid = [True] * len(column)
    error_messages = [None] * len(column)

    for error in errors:
        if error['row'] - 2 < len(is_valid):
            is_valid[error['row'] - 2] = False
            error_messages[error['row'] - 2] = error['error']

    logger.info(f"Проверка орфографии: найдено ошибок в {rows_with_errors} из {len(column)} строк")
    return {"is_valid": is_valid, "errors": error_messages, "total_errors": rows_with_errors}

# Оставляем старую функцию validate для обратной совместимости,
# но она будет просто вызывать новую.
def validate(value, params=None):
    # Эта функция не будет вызываться, если NEEDS_COLUMN_ACCESS=True,
    # но оставим ее для надежности.
    if pd.isna(value) or str(value).strip() == "":
        return True

    result = validate_column(pd.Series([value]), params)

    is_valid_flag = result["is_valid"][0] if result["is_valid"] else True
    error_list = [result["errors"][0]] if result["errors"] and result["errors"][0] else None

    return {"is_valid": is_valid_flag, "errors": error_list}

def reload_custom_dictionary():
    """
    Перезагружает слова из файла custom_dictionary.txt.
    Примечание: эта функция не будет напрямую использоваться новым правилом,
    т.к. словарь теперь можно задавать в параметрах.
    Но мы ее оставим для потенциальной обратной совместимости
    или для других правил.
    """
    try:
        dict_path = "custom_dictionary.txt"
        if SpellChecker(language='ru').word_frequency.load_text_file(dict_path):
             logger.info(f"Пользовательский словарь '{dict_path}' успешно перезагружен.")
        else:
             logger.warning(f"Не удалось найти или загрузить пользовательский словарь: {dict_path}")
    except Exception as e:
        logger.error(f"Ошибка при перезагрузке пользовательского словаря: {e}", exc_info=True)
