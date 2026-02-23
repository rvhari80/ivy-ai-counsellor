"""
Custom exception classes for the application.
"""


class IVYBaseException(Exception):
    """Base exception for IVY AI Counsellor application."""
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ConfigurationException(IVYBaseException):
    """Raised when application configuration is invalid or missing."""
    pass


class RateLimitException(IVYBaseException):
    """Raised when rate limit is exceeded."""
    pass


class RAGException(IVYBaseException):
    """Raised when RAG service encounters an error."""
    pass


class IntentClassificationException(IVYBaseException):
    """Raised when intent classification fails."""
    pass


class NotificationException(IVYBaseException):
    """Raised when notification sending fails."""
    pass


class PDFProcessingException(IVYBaseException):
    """Raised when PDF processing fails."""
    pass


class DatabaseException(IVYBaseException):
    """Raised when database operations fail."""
    pass


class ValidationException(IVYBaseException):
    """Raised when input validation fails."""
    pass
