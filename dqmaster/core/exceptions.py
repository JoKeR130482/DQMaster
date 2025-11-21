class DQMasterError(Exception):
    """Базовый класс для ошибок приложения"""
    pass

class ProjectNotFoundError(DQMasterError):
    """Проект не найден"""
    pass

class ValidationError(DQMasterError):
    """Ошибка валидации данных"""
    pass

class FileProcessingError(DQMasterError):
    """Ошибка обработки файла"""
    pass

class SecurityError(DQMasterError):
    """Ошибка безопасности"""
    pass
