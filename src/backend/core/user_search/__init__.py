"""User search: who the share modal suggests when typing a name or an email.

The backend is pluggable (settings.USER_SEARCH), following django-lasuite's
handler pattern (see lasuite.marketing) so the module can move there later:
the local backend searches Drive's users, the Contacts backend asks the
Contacts app for the user's own contacts.
"""

from django.utils.functional import LazyObject, empty

from .handler import UserSearchHandler


class DefaultUserSearch(LazyObject):
    """Lazy object to handle the user search backend."""

    def _setup(self):
        """Configure the user search backend."""
        self._wrapped = user_search_handler()


user_search_handler = UserSearchHandler()
user_search = DefaultUserSearch()


def reset_user_search():
    """Forget the configured backend, so the next use reads the settings again.

    For tests that change settings.USER_SEARCH.
    """
    global user_search_handler  # noqa: PLW0603  # pylint: disable=global-statement
    user_search_handler = UserSearchHandler()
    user_search._wrapped = empty  # noqa: SLF001  # pylint: disable=protected-access
