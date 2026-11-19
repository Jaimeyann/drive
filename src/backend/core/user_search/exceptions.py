"""User search exceptions."""


class UserSearchError(Exception):
    """Base exception for all user search exceptions."""


class UserSearchInvalidBackendError(UserSearchError):
    """The configured backend can't be imported."""


class UserSearchUnavailableError(UserSearchError):
    """The backend can't answer now (service down, slow, token refused)."""
