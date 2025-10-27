import os
import re
import pandas as pd
from spellchecker import SpellChecker
import asyncio
from typing import Optional

RULE_NAME = "Проверка орфографии"
RULE_DESC = "Значение содержит слова с орфографическими ошибками"
IS_CONFIGURABLE = False

spell: Optional[SpellChecker] = None
custom_dictionary_path = os.path.join(os.path.dirname(__file__), '..', 'custom_dictionary.txt')
WORD_REGEX = re.compile(r'[а-яА-ЯёЁ]+')

def _load_dictionary_sync() -> SpellChecker:
    new_spell = SpellChecker(language='ru')
    if os.path.exists(custom_dictionary_path):
        new_spell.word_frequency.load_text_file(custom_dictionary_path)
    return new_spell

async def reload_custom_dictionary():
    global spell
    loop = asyncio.get_running_loop()
    spell = await loop.run_in_executor(None, _load_dictionary_sync)
    print("DEBUG: Custom dictionary for spell_check reloaded asynchronously via direct import.")

def validate(value):
    if spell is None:
        return {"is_valid": True, "errors": None}

    if pd.isna(value) or not isinstance(value, str) or not value.strip():
        return {"is_valid": True, "errors": None}

    words = WORD_REGEX.findall(value)
    if not words:
        return {"is_valid": True, "errors": None}

    misspelled_original_case = []
    words_lower = [w.lower() for w in words]
    unknown_lower = spell.unknown(words_lower)

    if unknown_lower:
        lower_to_original_map = {w.lower(): w for w in words}
        for low_word in unknown_lower:
            if low_word in lower_to_original_map:
                original_word = lower_to_original_map[low_word]
                if original_word not in misspelled_original_case:
                    misspelled_original_case.append(original_word)

    if misspelled_original_case:
        return {"is_valid": False, "errors": misspelled_original_case}

    return {"is_valid": True, "errors": None}
