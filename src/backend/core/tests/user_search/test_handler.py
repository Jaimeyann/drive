"""The user search handler builds the backend from settings.USER_SEARCH."""

from django.core.exceptions import ImproperlyConfigured

import pytest

from core.user_search import reset_user_search, user_search
from core.user_search.backends.contacts import ContactsUserSearchBackend
from core.user_search.backends.local import LocalUserSearchBackend
from core.user_search.exceptions import UserSearchInvalidBackendError
from core.user_search.handler import UserSearchHandler


def test_the_default_backend_is_the_local_one():
    """Without configuration, Drive searches its own users."""
    assert isinstance(user_search, LocalUserSearchBackend)


def test_the_backend_and_its_parameters_come_from_the_settings(settings):
    """BACKEND is imported and PARAMETERS passed to it."""
    settings.USER_SEARCH = {
        "BACKEND": "core.user_search.backends.contacts.ContactsUserSearchBackend",
        "PARAMETERS": {"base_url": "https://contacts.example.org/", "timeout": 5},
    }
    reset_user_search()

    assert isinstance(user_search, ContactsUserSearchBackend)
    assert user_search.base_url == "https://contacts.example.org"
    assert user_search.timeout == 5


def test_a_handler_takes_its_own_definition():
    """A handler can be given a definition instead of the settings."""
    backend = UserSearchHandler(
        {"BACKEND": "core.user_search.backends.local.LocalUserSearchBackend"}
    )()

    assert isinstance(backend, LocalUserSearchBackend)


def test_an_unknown_backend_is_refused():
    """An unknown backend path is a configuration error."""
    with pytest.raises(UserSearchInvalidBackendError):
        UserSearchHandler({"BACKEND": "core.user_search.backends.nope.Nope"})()


def test_missing_settings_are_a_configuration_error(settings):
    """settings.USER_SEARCH is required."""
    del settings.USER_SEARCH

    with pytest.raises(ImproperlyConfigured):
        UserSearchHandler()()
