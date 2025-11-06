import os
import re
import pandas as pd
from spellchecker import SpellChecker

RULE_NAME = "Проверка орфографии"
RULE_DESC = "Значение содержит слова с орфографическими ошибками"
IS_CONFIGURABLE = False # Это правило не имеет настраиваемых параметров

# --- Глобальные переменные ---
spell = SpellChecker(language='ru')
# Добавим и английский словарь для проверки смешанных текстов
spell_en = SpellChecker(language='en')
custom_dictionary_path = os.path.join(os.path.dirname(__file__), '..', 'custom_dictionary.txt')
# Обновленное регулярное выражение для слов, включая слова с дефисами, апострофами и латиницу
WORD_REGEX = re.compile(r"[a-zA-Zа-яА-ЯёЁ]+(?:['’-][a-zA-Zа-яА-ЯёЁ]+)*")

def reload_custom_dictionary():
    """
    Перезагружает пользовательский словарь для всех языков.
    """
    global spell, spell_en
    spell = SpellChecker(language='ru')
    spell_en = SpellChecker(language='en')
    if os.path.exists(custom_dictionary_path):
        spell.word_frequency.load_text_file(custom_dictionary_path)
        spell_en.word_frequency.load_text_file(custom_dictionary_path)
    print("DEBUG: Custom dictionary for spell_check reloaded for all languages.")


# --- Вспомогательные функции ---
def is_sentence_start(text, word_start_index):
    """
    Проверяет, является ли слово началом предложения.
    Началом предложения считается:
    - Начало строки.
    - Позиция после точки, восклицательного или вопросительного знака,
      за которыми могут следовать пробелы.
    """
    if word_start_index == 0:
        return True

    # Ищем предшествующий не-пробельный символ
    prev_char_index = word_start_index - 1
    while prev_char_index >= 0 and text[prev_char_index].isspace():
        prev_char_index -= 1

    if prev_char_index < 0:
        # Если вся строка до слова - это пробелы, считаем началом предложения
        return True

    prev_char = text[prev_char_index]

    # Если предыдущий символ - это знак конца предложения
    if prev_char in '.!?':
        return True

    return False

# --- Логика валидации ---
def validate(value):
    """
    Проверяет орфографию каждого слова в строке с учетом новых правил.
    - Игнорирует акронимы (слова в верхнем регистре).
    - Корректно обрабатывает слова в начале предложения.
    - Проверяет кириллические и латинские слова по разным словарям.
    """
    if pd.isna(value) or not isinstance(value, str) or not value.strip():
        return {"is_valid": True, "errors": None}

    misspelled_original_case = set()

    # Словари для слов, которые нужно проверить
    words_to_check_ru = set()
    words_to_check_en = set()

    # Отображение из слова в нижнем регистре на оригинальное написание
    lower_to_original_map = {}

    # Используем finditer для получения индекса каждого слова
    for match in WORD_REGEX.finditer(value):
        word = match.group(0)
        start_index = match.start()

        # 1. Игнорируем акронимы (все буквы заглавные и длина > 1)
        if word.isupper() and len(word) > 1:
            continue

        word_lower = word.lower()

        # Сохраняем первое оригинальное написание слова
        if word_lower not in lower_to_original_map:
            lower_to_original_map[word_lower] = word

        # 2. Обработка слов в начале предложения
        if is_sentence_start(value, start_index):
            # Если слово в начале предложения и начинается с заглавной,
            # то для проверки используется его строчная версия.
            # Оригинальное слово (с заглавной) не трогаем, т.к. оно может быть верным.
            pass # Логика ниже уже работает с word_lower

        # 3. Разделение по языкам
        if re.search(r'[а-яА-ЯёЁ]', word):
            words_to_check_ru.add(word_lower)
        elif re.search(r'[a-zA-Z]', word):
            words_to_check_en.add(word_lower)

    # 4. Массовая проверка слов
    if words_to_check_ru:
        unknown_ru = spell.unknown(words_to_check_ru)
        for misspelled_word in unknown_ru:
             misspelled_original_case.add(lower_to_original_map[misspelled_word])

    if words_to_check_en:
        unknown_en = spell_en.unknown(words_to_check_en)
        for misspelled_word in unknown_en:
            misspelled_original_case.add(lower_to_original_map[misspelled_word])

    if misspelled_original_case:
        return {"is_valid": False, "errors": sorted(list(misspelled_original_case))}

    return {"is_valid": True, "errors": None}

# --- Инициализация при первом импорте ---
reload_custom_dictionary()