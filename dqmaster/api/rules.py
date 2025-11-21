from fastapi import APIRouter, HTTPException
from typing import List
from services.rule_service import RuleService
from models.rules import RuleMetadata
import logging

logger = logging.getLogger("dqmaster")
router = APIRouter()

# Инициализация сервиса правил
rule_service = RuleService()

@router.get("/rules")
async def get_all_rules() -> List[RuleMetadata]:
    """Получение списка всех правил"""
    try:
        return rule_service.get_all_rules()
    except Exception as e:
        logger.error(f"Ошибка при получении правил: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
