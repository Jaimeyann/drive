"""User search backend base module."""

from abc import ABC, abstractmethod

from . import UserSearchResult


class BaseUserSearchBackend(ABC):
    """Base class for all user search backends."""

    # Whether search() needs the user's OIDC access token (stored in the
    # session at login, OIDC_STORE_ACCESS_TOKEN).
    requires_access_token = False
    # Shorter queries answer nothing.
    min_query_length = 1

    @abstractmethod
    def search(
        self, user, query: str, *, limit: int, access_token: str | None = None
    ) -> list[UserSearchResult]:
        """
        Search the people *user* may share with.

        Args:
            user: The user searching
            query: What they typed
            limit: Maximum number of results
            access_token: The user's OIDC access token, if the backend needs it

        Returns:
            list[UserSearchResult]: Best first

        Raises:
            UserSearchUnavailableError: If the backend can't answer now
        """

    def record_share(self, user, emails: list[str], *, access_token: str | None = None):  # pylint: disable=unused-argument
        """Tell the backend *user* just shared with *emails* (best effort).

        Lets a backend rank these people higher next time. Never raises.
        Backends that don't rank people have nothing to do.
        """
        return None
