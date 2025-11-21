import json
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime
import pandas as pd
import io
import asyncio
from core.config import settings
from core.security import SecurityValidator
from core.exceptions import ProjectNotFoundError, FileProcessingError
from models.project import Project, ProjectInfo, FileSchema, SheetSchema, FieldSchema
import logging

logger = logging.getLogger("dqmaster")

class ProjectService:
    """Сервис для работы с проектами"""

    @staticmethod
    async def get_projects() -> List[ProjectInfo]:
        """Получение списка проектов"""
        projects = []
        if not settings.PROJECTS_DIR.exists():
            return projects

        for project_dir in settings.PROJECTS_DIR.iterdir():
            if project_dir.is_dir():
                try:
                    project = await ProjectService.read_project(project_dir.name)
                    if project:
                        total_size = sum(f.stat().st_size for f in project_dir.glob('**/*') if f.is_file())
                        project_info = ProjectInfo(
                            id=project.id,
                            name=project.name,
                            description=project.description,
                            updated_at=project.updated_at,
                            size_kb=round(total_size / 1024, 2)
                        )
                        projects.append(project_info)
                except Exception as e:
                    logger.warning(f"Error reading project {project_dir.name}: {e}")
                    continue

        projects.sort(key=lambda p: p.updated_at, reverse=True)
        return projects

    @staticmethod
    async def create_project(project_data: Dict[str, Any]) -> Project:
        """Создание нового проекта"""
        project_id = str(uuid.uuid4())
        project_dir = settings.PROJECTS_DIR / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "files").mkdir(exist_ok=True)

        now = datetime.utcnow().isoformat()
        project = Project(
            id=project_id,
            name=project_data["name"],
            description=project_data.get("description", ""),
            created_at=now,
            updated_at=now,
            files=[],
            auto_revalidate=True
        )

        # Сохраняем конфигурацию проекта
        config_path = project_dir / "project.json"
        config_path.write_text(json.dumps(project.dict(), indent=2, ensure_ascii=False), encoding="utf-8")

        return project

    @staticmethod
    async def read_project(project_id: str) -> Optional[Project]:
        """Чтение проекта по ID"""
        SecurityValidator.validate_project_id(project_id)
        config_path = settings.PROJECTS_DIR / project_id / "project.json"

        if not config_path.exists():
            raise ProjectNotFoundError(f"Проект с ID {project_id} не найден")

        try:
            return Project(**json.loads(config_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error reading project config for {project_id}: {e}")
            raise ProjectNotFoundError(f"Конфигурация проекта повреждена: {str(e)}")

    @staticmethod
    async def write_project(project_id: str, project_data: Project):
        """Запись данных проекта"""
        SecurityValidator.validate_project_id(project_id)
        config_path = settings.PROJECTS_DIR / project_id / "project.json"

        project_data.updated_at = datetime.utcnow().isoformat()
        config_path.write_text(json.dumps(project_data.dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    async def upload_file_to_project(project_id: str, file_content: bytes, filename: str) -> Project:
        """Загрузка файла в проект"""
        SecurityValidator.validate_project_id(project_id)

        # Проверка типа файла
        if not (filename.endswith('.xlsx') or filename.endswith('.xls')):
            raise ValueError("Недопустимый тип файла. Разрешены только Excel файлы (.xlsx, .xls)")

        # Проверка размера файла
        if len(file_content) > settings.MAX_FILE_SIZE:
            raise ValueError(f"Размер файла превышает лимит в {settings.MAX_FILE_SIZE // (1024 * 1024)} MB")

        project = await ProjectService.read_project(project_id)
        if not project:
            raise ProjectNotFoundError(f"Проект с ID {project_id} не найден")

        project_files_dir = settings.PROJECTS_DIR / project_id / "files"
        project_files_dir.mkdir(exist_ok=True)

        try:
            # Чтение Excel файла
            xls = pd.ExcelFile(io.BytesIO(file_content))
            sheets = []

            # Проверка количества строк
            total_rows = 0
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                total_rows += len(df)
                if total_rows > settings.MAX_EXCEL_ROWS:
                    raise ValueError(f"Excel файл превышает максимальное количество строк ({settings.MAX_EXCEL_ROWS})")

            # Создание схемы для каждого листа
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                fields = [FieldSchema(name=col) for col in df.columns]
                sheets.append(SheetSchema(name=sheet_name, fields=fields))

            # Сохранение файла
            saved_filename = f"{uuid.uuid4()}{Path(filename).suffix}"
            file_path = project_files_dir / saved_filename
            file_path.write_bytes(file_content)

            # Добавление файла в проект
            new_file = FileSchema(
                name=filename,
                saved_name=saved_filename,
                sheets=sheets
            )

            if "files" not in project.__dict__ or project.files is None:
                project.files = []
            project.files.append(new_file)

            # Сохранение обновленного проекта
            await ProjectService.write_project(project_id, project)

            return project
        except Exception as e:
            logger.error(f"Error processing Excel file: {e}")
            raise FileProcessingError(f"Не удалось обработать Excel файл: {str(e)}")

    @staticmethod
    async def delete_project(project_id: str):
        """Удаление проекта"""
        SecurityValidator.validate_project_id(project_id)
        project_dir = settings.PROJECTS_DIR / project_id

        if not project_dir.is_dir():
            raise ProjectNotFoundError(f"Проект с ID {project_id} не найден")

        shutil.rmtree(project_dir)
