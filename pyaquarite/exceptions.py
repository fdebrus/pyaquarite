class AquariteError(Exception):
    """Base exception for Aquarite errors."""

class AuthenticationError(AquariteError):
    """Authentication failure."""

class RequestError(AquariteError):
    """API Request failure."""
