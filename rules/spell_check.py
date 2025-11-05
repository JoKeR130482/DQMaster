import os
import re
import pandas as pd
from spellchecker import SpellChecker

RULE_NAME = "Проверка орфографии"
RULE_DESC = "Значение содержит слова с орфографическими ошибками"
IS_CONFIGURABLE = False # Это правило не имеет настраиваемых параметров

# --- Глобальные переменные ---
spell_ru = SpellChecker(language='ru')
spell_en = SpellChecker(language='en')
custom_dictionary_path = os.path.join(os.path.dirname(__file__), '..', 'custom_dictionary.txt')
# Регулярное выражение для поиска слов, включая слова с дефисами, апострофами и латинские буквы
WORD_REGEX = re.compile(r"[a-zA-Zа-яА-ЯёЁ]+(?:['’-][a-zA-Zа-яА-ЯёЁ]+)*")

def reload_custom_dictionary():
    """
    Перезагружает пользовательский словарь.
    """
    global spell_ru
    spell_ru = SpellChecker(language='ru')
    if os.path.exists(custom_dictionary_path):
        spell_ru.word_frequency.load_text_file(custom_dictionary_path)
    print("DEBUG: Custom dictionary for spell_check reloaded.")


def is_sentence_start(text, word_start_index):
    """
    Проверяет, является ли слово в указанной позиции началом предложения.
    Началом предложения считается:
    - Самое первое слово в тексте.
    - Слово, которому предшествует знак конца предложения (.?!) и, возможно, пробелы.
    """
    if word_start_index == 0:
        return True

    # Ищем предшествующий не-пробельный символ
    idx = word_start_index - 1
    while idx >= 0 and text[idx].isspace():
        idx -= 1

    # Если мы дошли до начала строки, не найдя символа, значит это начало
    if idx < 0:
        return True

    # Проверяем, является ли предшествующий символ знаком окончания предложения
    return text[idx] in '.?!'

# --- Логика валидации ---
def validate(value):
    """
    Проверяет орфографию каждого слова в строке с учетом новых правил.
    Возвращает словарь:
    {
        "is_valid": bool,
        "errors": list[str] | None
    }
    """
    if pd.isna(value) or not isinstance(value, str) or not value.strip():
        return {"is_valid": True, "errors": None}

    matches = list(WORD_REGEX.finditer(value))
    if not matches:
        return {"is_valid": True, "errors": None}

    misspelled_original_case = []

    for match in matches:
        word = match.group(0)
        word_start_index = match.start()

        # 1. Пропускаем акронимы
        if word.isupper() and len(word) > 1:
            continue

        word_lower = word.lower()

        # 2. Обработка составных слов (с дефисом или апострофом)
        # Разделяем слово на части и проверяем каждую часть
        if '-' in word or "'" in word or "’" in word:
            parts = re.split("[-'’]", word_lower)
            all_parts_known = True
            for part in parts:
                if not part: continue
                is_cyrillic_part = bool(re.search('[а-яё]', part))

                if is_cyrillic_part:
                    if part not in spell_ru:
                        all_parts_known = False
                        break
                else: # Латиница
                    if part not in spell_en:
                        all_parts_known = False
                        break
            if all_parts_known:
                continue


        # Определяем язык слова
        is_cyrillic = bool(re.search('[а-яА-ЯёЁ]', word))
        is_latin = bool(re.search('[a-zA-Z]', word))

        if is_cyrillic and is_latin:
            continue

        # 3. Обработка начала предложения
        if word[0].isupper() and is_sentence_start(value, word_start_index):
            checker = spell_ru if is_cyrillic else spell_en
            if word_lower in checker:
                 continue

        # 4. Основная проверка
        checker = spell_ru if is_cyrillic else spell_en
        if word_lower not in checker:
            if word not in misspelled_original_case:
                misspelled_original_case.append(word)

    if misspelled_original_case:
        return {"is_valid": False, "errors": misspelled_original_case}

    return {"is_valid": True, "errors": None}

# --- Инициализация при первом импорте ---
reload_custom_dictionary()