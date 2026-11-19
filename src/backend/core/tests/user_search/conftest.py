"""Fixtures for the user search tests."""

import time

import pytest
from rest_framework.test import APIClient

from core import factories
from core.user_search import reset_user_search

CONTACTS_URL = "https://contacts.example.org"
SEARCH_URL = f"{CONTACTS_URL}/external_api/v1.0/search/"
INTERACTIONS_URL = f"{CONTACTS_URL}/external_api/v1.0/interactions/"
ACCESS_TOKEN = "user-access-token"


@pytest.fixture(autouse=True)
def fresh_user_search():
    """Each test reads settings.USER_SEARCH again."""
    reset_user_search()
    yield
    reset_user_search()


@pytest.fixture(name="contacts_backend")
def contacts_backend_fixture(settings):
    """Configure the Contacts backend."""
    settings.USER_SEARCH = {
        "BACKEND": "core.user_search.backends.contacts.ContactsUserSearchBackend",
        "PARAMETERS": {"base_url": CONTACTS_URL},
    }
    settings.OIDC_STORE_ACCESS_TOKEN = True
    reset_user_search()


def card(name, *emails, pref=None):
    """A JSContact card as Contacts' search returns it."""
    entries = {}
    for index, address in enumerate(emails, start=1):
        entry = {"address": address}
        if pref == index or (pref is None and index == 1):
            entry["pref"] = 1
        entries[f"e{index}"] = entry
    return {
        "@type": "Card",
        "version": "1.0",
        "uid": f"urn:uuid:{name}",
        "kind": "individual",
        "name": {"full": name},
        "emails": entries,
    }


def logged_in_client(user, *, access_token=ACCESS_TOKEN, expires_in=3600):
    """A client logged in as *user*, with an OIDC access token in its session."""
    client = APIClient()
    # Logged in through OIDC, like real users: only those sessions refresh.
    client.force_login(user, backend="core.authentication.backends.OIDCAuthenticationBackend")
    session = client.session
    if access_token:
        session["oidc_access_token"] = access_token
    session["oidc_id_token_expiration"] = time.time() + expires_in
    session.save()
    return client


@pytest.fixture(name="user")
def user_fixture():
    """The user searching."""
    return factories.UserFactory(email="alice@example.org")
