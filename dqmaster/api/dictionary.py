from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List
import logging
from pathlib import Path
from core.config import settings

logger = logging.getLogger("dqmaster")
router = APIRouter()

CUSTOM_DICT_PATH = settings.CUSTOM_DICT_PATH

class AddWordRequest(BaseModel):
    word: str

@router.get("/dictionary", response_model=List[str])
async def get_dictionary():
    """Получение списка слов из пользовательского словаря"""
    if not CUSTOM_DICT_PATH.exists():
        return []

    try:
        words = CUSTOM_DICT_PATH.read_text(encoding="utf-8").strip().split("\n")
        return sorted([word.strip() for word in words if word.strip() and not word.strip().startswith('#')])
    except Exception as e:
        logger.error(f"Ошибка при чтении словаря: {str(e)}")
        raise HTTPException(status_code=500, detail="Не удалось прочитать словарь")

@router.post("/dictionary", status_code=201)
async def add_word_to_dictionary(request: AddWordRequest):
    """Добавление слова в пользовательский словарь"""
    new_word = request.word.strip().lower()
    if not new_word:
        raise HTTPException(status_code=400, detail="Слово не может быть пустым")

    try:
        # Получаем текущий словарь
        current_words = await get_dictionary()
        if new_word in [w.lower() for w in current_words]:
            raise HTTPException(status_code=400, detail="Слово уже существует в словаре")

        # Добавляем новое слово
        with CUSTOM_DICT_PATH.open("a", encoding="utf-8") as f:
            f.write(f"\n{new_word}")

        return {"message": "Слово успешно добавлено"}
    except Exception as e:
        logger.error(f"Ошибка при добавлении слова в словарь: {str(e)}")
        raise HTTPException(status_code=500, detail="Не удалось добавить слово в словарь")
