from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import asyncio
from core.exceptions import ProjectNotFoundError, ValidationError
from services.validation_service import ValidationService
from services.rule_service import RuleService
from services.project_service import ProjectService
import logging

logger = logging.getLogger("dqmaster")
router = APIRouter()

# Инициализация сервиса правил
rule_service = RuleService()

@router.post("/projects/{project_id}/validate")
async def validate_project_data(project_id: str):
    """
    Запускает валидацию данных проекта
    """
    try:
        project = await ProjectService.read_project(project_id)
        if not project:
            raise ProjectNotFoundError(f"Проект {project_id} не найден")

        # Проверка, не запущена ли уже валидация
        if await ValidationService.get_validation_status(project_id):
            current_status = await ValidationService.get_validation_status(project_id)
            if current_status.get("is_running"):
                raise ValidationError("Валидация уже выполняется для этого проекта")

        # Запуск валидации в фоновом режиме
        asyncio.create_task(ValidationService.start_validation(project_id, rule_service))

        # Возврат начального статуса
        return {
            "status": "started",
            "project_id": project_id,
            "initial_status": {
                "is_running": True,
                "percentage": 0.0,
                "processed_rows": 0,
                "message": "Запуск проверки...",
                "current_file": "",
                "current_sheet": "",
                "current_field": "",
                "current_rule": ""
            }
        }
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при запуске валидации для проекта {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@router.get("/projects/{project_id}/validation-status")
async def get_validation_status(project_id: str):
    """Возвращает текущее состояние проверки"""
    try:
        return await ValidationService.get_validation_status(project_id)
    except Exception as e:
        logger.error(f"Ошибка при получении статуса валидации для проекта {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
