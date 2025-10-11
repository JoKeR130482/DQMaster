import os
import re
import pandas as pd
from spellchecker import SpellChecker

RULE_NAME = "Проверка орфографии"
RULE_DESC = "Значение содержит слова с орфографическими ошибками"

# --- Глобальные переменные ---
spell = SpellChecker(language='ru')
custom_dictionary_path = os.path.join(os.path.dirname(__file__), '..', 'custom_dictionary.txt')
WORD_REGEX = re.compile(r'[а-яА-ЯёЁ]+')

def reload_custom_dictionary():
    """
    Перезагружает пользовательский словарь.
    Сначала очищает текущий словарь, затем загружает стандартный и пользовательский.
    """
    global spell
    # Создаем новый экземпляр, чтобы сбросить все слова, включая старые пользовательские
    spell = SpellChecker(language='ru')
    if os.path.exists(custom_dictionary_path):
        spell.word_frequency.load_text_file(custom_dictionary_path)
    print("DEBUG: Custom dictionary reloaded.")


# --- Логика валидации ---
def validate(value):
    """
    Проверяет орфографию каждого слова в строке.
    Возвращает словарь:
    {
        "is_valid": bool,
        "errors": list[str] | None
    }
    """
    # 1. Если значение пустое или не строка, считаем его корректным
    if pd.isna(value) or not isinstance(value, str) or not value.strip():
        return {"is_valid": True, "errors": None}

    # 2. Извлекаем все слова из строки, сохраняя оригинальный регистр
    words = WORD_REGEX.findall(value)
    if not words:
        return {"is_valid": True, "errors": None}

    # 3. Находим слова, которых нет в словаре (проверяем в нижнем регистре)
    misspelled_original_case = []
    words_lower = [w.lower() for w in words]
    unknown_lower = spell.unknown(words_lower)

    # 4. Сопоставляем найденные ошибки с оригинальными словами
    if unknown_lower:
        lower_to_original_map = {w.lower(): w for w in words}
        for low_word in unknown_lower:
            if low_word in lower_to_original_map:
                original_word = lower_to_original_map[low_word]
                if original_word not in misspelled_original_case:
                    misspelled_original_case.append(original_word)

    # 5. Если есть хотя бы одно неизвестное слово, возвращаем ошибку
    if misspelled_original_case:
        return {"is_valid": False, "errors": misspelled_original_case}

    return {"is_valid": True, "errors": None}

# --- Инициализация при первом импорте ---
reload_custom_dictionary()