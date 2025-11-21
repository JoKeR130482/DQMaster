import re
from pathlib import Path
from fastapi import HTTPException, status
from .config import settings

class SecurityValidator:
    """Проверка безопасности входных данных"""

    # Регулярка для валидации project_id (только UUID)
    UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

    @classmethod
    def validate_project_id(cls, project_id: str) -> str:
        """Проверка идентификатора проекта"""
        if not project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Идентификатор проекта не может быть пустым"
            )

        if not cls.UUID_PATTERN.match(project_id.lower()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат идентификатора проекта. Он должен быть в формате UUID."
            )

        return project_id.lower()

    @classmethod
    def safe_path_join(cls, base_path: Path, *path_parts: str) -> Path:
        """
        Безопасное объединение путей с защитой от Path Traversal
        """
        # Преобразуем все части пути в безопасный формат
        safe_parts = []
        for part in path_parts:
            # Удаляем опасные последовательности
            cleaned = str(part).replace("..", "").replace("//", "/").strip("/").replace("\\", "")
            if cleaned:
                safe_parts.append(cleaned)

        result_path = base_path.joinpath(*safe_parts)

        # Проверяем, что результат находится внутри базовой директории
        try:
            result_path.resolve().relative_to(base_path.resolve())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный путь - возможная попытка обхода каталога"
            )

        return result_path
