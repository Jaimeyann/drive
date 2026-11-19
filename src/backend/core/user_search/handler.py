"""User search backend handler."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.functional import cached_property
from django.utils.module_loading import import_string

from .exceptions import UserSearchInvalidBackendError


class UserSearchHandler:
    """User search handler managing the backend instantiation."""

    def __init__(self, backend=None):
        """Initialize the user search handler."""
        # backend is an optional dict of user search backend definitions
        # (structured like settings.USER_SEARCH).
        self._backend = backend
        self._user_search = None

    @cached_property
    def backend(self):
        """Put in cache the backend properties from the settings."""
        if self._backend is None:
            try:
                self._backend = settings.USER_SEARCH.copy()
            except AttributeError as e:
                raise ImproperlyConfigured("settings.USER_SEARCH is not configured") from e
        return self._backend

    def __call__(self):
        """Create if not existing the backend and then return it."""
        if self._user_search is None:
            self._user_search = self.create_user_search(self.backend)
        return self._user_search

    def create_user_search(self, params):
        """Instantiate and configure the user search backend."""
        params = params.copy()
        backend = params.pop("BACKEND")
        parameters = params.pop("PARAMETERS", {})
        try:
            klass = import_string(backend)
        except ImportError as e:
            raise UserSearchInvalidBackendError(f"Could not find backend {backend!r}: {e}") from e
        return klass(**parameters)
