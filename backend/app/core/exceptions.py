class DomainException(Exception):
    def __init__(self, message: str, status_code: int = 500, code: str = "INTERNAL_ERROR", headers: dict | None = None):
        self.message = message
        self.status_code = status_code
        self.code = code
        self.headers = headers
        super().__init__(self.message)

class ModelWeightsNotFoundError(DomainException):
    def __init__(self):
        super().__init__(message="Decision matrix classification payload file missing on disk.", status_code=503, code="MODEL_IO_NOT_FOUND")

class AuthenticationError(DomainException):
    def __init__(self, message: str = "Not authenticated."):
        super().__init__(message=message, status_code=401, code="AUTH_INVALID")

class PermissionDeniedError(DomainException):
    def __init__(self):
        super().__init__(message="You do not have permission to do this.", status_code=403, code="FORBIDDEN")

class EmailAlreadyRegisteredError(DomainException):
    def __init__(self):
        super().__init__(message="An account with this email already exists.", status_code=409, code="EMAIL_TAKEN")

class NotFoundError(DomainException):
    def __init__(self, what: str = "Item"):
        super().__init__(message=f"{what} not found.", status_code=404, code="NOT_FOUND")

class ConflictError(DomainException):
    def __init__(self, message: str):
        super().__init__(message=message, status_code=409, code="CONFLICT")

class RateLimitError(DomainException):
    def __init__(self, retry_after: int):
        super().__init__(message=f"Too many attempts. Try again in {retry_after} seconds.", status_code=429,
                         code="RATE_LIMITED", headers={"Retry-After": str(retry_after)})
