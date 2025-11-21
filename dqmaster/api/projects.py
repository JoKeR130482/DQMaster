from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from typing import List, Optional
import json
from models.project import ProjectInfo, ProjectCreateRequest, ProjectPartialUpdateRequest, Project
from services.project_service import ProjectService
from core.exceptions import ProjectNotFoundError
import logging

logger = logging.getLogger("dqmaster")
router = APIRouter()

@router.get("/projects", response_model=List[ProjectInfo])
async def get_projects():
    """Получение списка проектов"""
    try:
        return await ProjectService.get_projects()
    except Exception as e:
        logger.error(f"Ошибка при получении проектов: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@router.post("/projects", status_code=201, response_model=Project)
async def create_project(project_data: ProjectCreateRequest):
    """Создание нового проекта"""
    try:
        return await ProjectService.create_project(project_data.dict())
    except Exception as e:
        logger.error(f"Ошибка при создании проекта: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@router.get("/projects/{project_id}", response_model=Project)
async def get_project_details(project_id: str):
    """Получение деталей проекта"""
    try:
        return await ProjectService.read_project(project_id)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при чтении проекта {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@router.post("/projects/{project_id}/upload", response_model=Project)
async def upload_file_to_project(project_id: str, file: UploadFile = File(...)):
    """Загрузка файла в проект"""
    try:
        contents = await file.read()
        return await ProjectService.upload_file_to_project(project_id, contents, file.filename)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при загрузке файла в проект {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: str):
    """Удаление проекта"""
    try:
        await ProjectService.delete_project(project_id)
        return None
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при удалении проекта {project_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
