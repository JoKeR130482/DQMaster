import os
import re
import pandas as pd
from spellchecker import SpellChecker

RULE_NAME = "Проверка орфографии"
RULE_DESC = "Значение содержит слова с орфографическими ошибками"

# --- Инициализация спелл-чекера (выполняется один раз при импорте) ---

# 1. Создаем объект спелл-чекера для русского языка
spell = SpellChecker(language='ru')

# 2. Загружаем пользовательский словарь
custom_dictionary_path = os.path.join(os.path.dirname(__file__), '..', 'custom_dictionary.txt')
if os.path.exists(custom_dictionary_path):
    spell.word_frequency.load_text_file(custom_dictionary_path)

# 3. Регулярное выражение для извлечения только кириллических слов
WORD_REGEX = re.compile(r'[а-яА-ЯёЁ]+')

# --- Логика валидации ---

def validate(value):
    """
    Проверяет орфографию каждого слова в строке.
    Возвращает True, если все слова корректны, иначе False.
    """
    # 1. Если значение пустое или не строка, считаем его корректным (за это отвечают другие правила)
    if pd.isna(value) or not isinstance(value, str) or not value.strip():
        return True

    # 2. Извлекаем все слова из строки, приводим к нижнему регистру
    words = WORD_REGEX.findall(value.lower())
    if not words:
        return True # Если слов нет (например, только цифры или символы), то и ошибок нет

    # 3. Ищем слова, которых нет в словаре
    misspelled = spell.unknown(words)

    # 4. Если есть хотя бы одно неизвестное слово, возвращаем False (ошибка)
    if misspelled:
        # Для отладки можно вывести некорректные слова:
        # print(f"Ошибки в словах: {misspelled}")
        return False

    return True