from fastapi import APIRouter, HTTPException
from typing import List
import json
from core.config import settings
from models.validation import RuleGroup
import logging

logger = logging.getLogger("dqmaster")
router = APIRouter()

RULE_GROUPS_PATH = settings.RULE_GROUPS_PATH

@router.get("/rule-groups", response_model=List[RuleGroup])
async def get_rule_groups():
    """Получение списка групп правил"""
    if not RULE_GROUPS_PATH.exists():
        return []

    try:
        groups_data = json.loads(RULE_GROUPS_PATH.read_text(encoding="utf-8"))
        return [RuleGroup(**group) for group in groups_data]
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Ошибка при чтении групп правил: {str(e)}")
        raise HTTPException(status_code=500, detail="Не удалось прочитать группы правил")

@router.post("/rule-groups", response_model=RuleGroup, status_code=201)
async def create_rule_group(group: RuleGroup):
    """Создание новой группы правил"""
    try:
        # Читаем текущие группы
        current_groups = await get_rule_groups()

        # Проверяем на дубликаты
        if any(g.id == group.id for g in current_groups):
            raise HTTPException(status_code=409, detail="Группа правил с таким ID уже существует")

        # Добавляем новую группу
        current_groups.append(group)

        # Сохраняем обновленный список
        RULE_GROUPS_PATH.write_text(json.dumps([g.dict() for g in current_groups], indent=2, ensure_ascii=False), encoding="utf-8")

        return group
    except Exception as e:
        logger.error(f"Ошибка при создании группы правил: {str(e)}")
        raise HTTPException(status_code=500, detail="Не удалось создать группу правил")
