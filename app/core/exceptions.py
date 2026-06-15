"""
Custom Application Exceptions
"""


class APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: dict = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NotFoundError(APIError):
    def __init__(self, resource: str, resource_id: str = ""):
        super().__init__(
            status_code=404,
            code=f"{resource.upper()}_NOT_FOUND",
            message=f"{resource} not found",
            details={"id": resource_id},
        )


class UnauthorizedError(APIError):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(status_code=401, code="UNAUTHORIZED", message=message)


class ForbiddenError(APIError):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(status_code=403, code="FORBIDDEN", message=message)


class ValidationError(APIError):
    def __init__(self, message: str, details: dict = None):
        super().__init__(status_code=422, code="VALIDATION_ERROR", message=message, details=details)


class AIAgentError(APIError):
    def __init__(self, agent: str, message: str, details: dict = None):
        super().__init__(
            status_code=500,
            code="AI_AGENT_ERROR",
            message=f"AI agent '{agent}' failed: {message}",
            details=details,
        )


class ResumeParseError(APIError):
    def __init__(self, message: str, details: dict = None):
        super().__init__(status_code=422, code="RESUME_PARSE_FAILED", message=message, details=details)


class DuplicateError(APIError):
    def __init__(self, resource: str):
        super().__init__(
            status_code=409,
            code=f"{resource.upper()}_ALREADY_EXISTS",
            message=f"{resource} already exists",
        )