import json
import pandas as pd
import io
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from core.config import settings
from core.security import SecurityValidator
from core.storage import status_storage, ValidationStatus as StorageValidationStatus
from core.exceptions import ProjectNotFoundError, ValidationError
from models.project import Project
from models.validation import ValidationResults, ValidationError as ValidationErrorModel
from services.project_service import ProjectService
import logging

logger = logging.getLogger("dqmaster")

class ValidationService:
    """Сервис для валидации данных"""

    @staticmethod
    async def get_validation_status(project_id: str) -> Dict[str, Any]:
        """Получение статуса валидации"""
        status = await status_storage.get_status(project_id)
        return {
            "is_running": status.is_running,
            "current_file": status.current_file,
            "current_sheet": status.current_sheet,
            "current_field": status.current_field,
            "current_rule": status.current_rule,
            "processed_rows": status.processed_rows,
            "total_rows": status.total_rows,
            "percentage": status.percentage,
            "message": status.message
        }

    @staticmethod
    async def _calculate_total_operations(project_id: str, project: Project) -> int:
        """Асинхронный расчет общего количества операций для прогресса"""
        total_ops = 0
        project_files_dir = settings.PROJECTS_DIR / project.id / "files"
        loop = asyncio.get_running_loop()

        try:
            for file_schema in project.files:
                file_path = project_files_dir / file_schema.saved_name
                if not file_path.exists():
                    continue

                xls_content = await loop.run_in_executor(None, file_path.read_bytes)
                xls = pd.ExcelFile(io.BytesIO(xls_content))

                for sheet_schema in file_schema.sheets:
                    if not sheet_schema.is_active:
                        continue

                    try:
                        df = pd.read_excel(xls, sheet_name=sheet_schema.name)
                        row_count = len(df)
                        rule_count = sum(len(field.rules) for field in sheet_schema.fields)
                        total_ops += row_count * rule_count
                    except Exception as e:
                        logger.warning(f"[{project_id}] Could not calculate ops for sheet {sheet_schema.name}: {e}")
                        continue
        except Exception as e:
            logger.error(f"[{project_id}] Error calculating total operations: {e}", exc_info=True)
            return 100

        if total_ops <= 0:
            logger.warning(f"[{project_id}] Total operations is 0. Setting to 100 for progress display.")
            return 100

        return total_ops

    @staticmethod
    async def _run_validation_async(project_id: str, rule_service):
        """Асинхронная функция для выполнения валидации"""
        try:
            await status_storage.set_status(project_id, StorageValidationStatus(
                is_running=True,
                percentage=0.0,
                processed_rows=0,
                message="Подготовка к валидации..."
            ))

            project = await ProjectService.read_project(project_id)
            if not project:
                await status_storage.set_status(project_id, StorageValidationStatus(
                    is_running=False,
                    message="Ошибка: проект не найден."
                ))
                return

            total_operations = await ValidationService._calculate_total_operations(project_id, project)

            await status_storage.set_status(project_id, StorageValidationStatus(
                is_running=True,
                total_rows=int(total_operations),
                message="Начинаем проверку...",
                percentage=1.0
            ))

            # Основная логика валидации будет добавлена в следующих итерациях
            # Здесь мы имитируем процесс валидации для демонстрации

            processed_ops_count = 0
            while processed_ops_count < total_operations:
                processed_ops_count += min(100, total_operations - processed_ops_count)
                percentage = min(99.0, (processed_ops_count / total_operations) * 100)

                await status_storage.set_status(project_id, StorageValidationStatus(
                    is_running=True,
                    processed_rows=processed_ops_count,
                    percentage=percentage,
                    message=f"Обработано {processed_ops_count} из {total_operations} операций"
                ))

                await asyncio.sleep(0.1)

            # Имитация сохранения результатов
            results_path = settings.PROJECTS_DIR / project_id / "validation_result.json"
            results_data = {
                "total_processed_rows": total_operations,
                "required_field_error_rows_count": 0,
                "required_field_errors": [],
                "file_results": [],
                "validated_at": datetime.utcnow().isoformat()
            }

            results_path.write_text(json.dumps(results_data, indent=2, ensure_ascii=False), encoding="utf-8")

            await status_storage.set_status(project_id, StorageValidationStatus(
                is_running=False,
                percentage=100.0,
                processed_rows=total_operations,
                message="Проверка завершена."
            ))

        except Exception as e:
            logger.error(f"[{project_id}] Error during validation: {e}", exc_info=True)
            await status_storage.set_status(project_id, StorageValidationStatus(
                is_running=False,
                message=f"Ошибка валидации: {str(e)}"
            ))

    @staticmethod
    async def start_validation(project_id: str, rule_service):
        """Запуск валидации в фоновом режиме"""
        if await status_storage.is_running(project_id):
            raise ValidationError("Валидация для этого проекта уже выполняется")

        asyncio.create_task(ValidationService._run_validation_async(project_id, rule_service))
