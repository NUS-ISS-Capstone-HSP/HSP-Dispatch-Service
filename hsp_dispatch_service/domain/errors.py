class DomainError(Exception):
    """Base domain error."""


class ValidationError(DomainError):
    """Raised when input validation fails."""


class NotFoundError(DomainError):
    """Raised when entity does not exist."""


class ConflictError(DomainError):
    """Raised when business state conflict happens."""


class ExternalServiceError(DomainError):
    """Raised when external service call fails."""
