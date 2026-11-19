"""GET /api/v1.0/users/ when the share modal suggests from Contacts."""

import pytest
import responses
from rest_framework.test import APIClient

from core import factories, models

from .conftest import ACCESS_TOKEN, SEARCH_URL, card, logged_in_client

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("contacts_backend")]

URL = "/api/v1.0/users/"


@responses.activate
def test_contacts_people_come_back_as_users_and_invitations(user):
    """Drive users keep their shape; other addresses use the invitation shape."""
    felix = factories.UserFactory(email="felix@example.org", full_name="Félix Marchand")
    responses.add(
        responses.GET,
        SEARCH_URL,
        json={"results": [card("Félix", "felix@example.org"), card("Marie", "marie@example.org")]},
    )

    response = logged_in_client(user).get(URL, {"q": "m"})

    assert response.status_code == 200
    first, second = response.json()
    assert first["id"] == str(felix.id)
    assert first["email"] == "felix@example.org"
    assert first["full_name"] == "Félix Marchand"
    # The share modal sends an invitation for a result whose id is its email.
    assert second == {
        "id": "marie@example.org",
        "email": "marie@example.org",
        "full_name": "Marie",
        "short_name": "",
    }
    assert responses.calls[0].request.headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"


@responses.activate
def test_one_letter_is_enough_with_contacts(user):
    """Contacts only searches the user's own book: short queries are fine."""
    responses.add(responses.GET, SEARCH_URL, json={"results": []})

    assert logged_in_client(user).get(URL, {"q": "m"}).status_code == 200
    assert len(responses.calls) == 1


def test_an_empty_query_answers_nothing(user):
    """No query, no call."""
    with responses.RequestsMock() as mock:
        assert logged_in_client(user).get(URL, {"q": ""}).json() == []
        assert not mock.calls


@responses.activate
def test_contacts_down_falls_back_to_drive_users(user):
    """When Contacts fails, the share modal still finds Drive's users."""
    john = factories.UserFactory(email="john.doe@example.org")
    responses.add(responses.GET, SEARCH_URL, status=503)

    response = logged_in_client(user).get(URL, {"q": "john.doe@example.org"})

    assert [found["id"] for found in response.json()] == [str(john.id)]


@responses.activate
def test_without_fallback_contacts_down_answers_nothing(user, settings):
    """fallback_to_local=False makes an outage visible instead."""
    settings.USER_SEARCH["PARAMETERS"]["fallback_to_local"] = False
    factories.UserFactory(email="john.doe@example.org")
    responses.add(responses.GET, SEARCH_URL, status=503)

    assert logged_in_client(user).get(URL, {"q": "john.doe@example.org"}).json() == []


def test_without_token_in_session_it_falls_back(user):
    """No stored token: Drive's users, and Contacts isn't called."""
    john = factories.UserFactory(email="john.doe@example.org")

    with responses.RequestsMock() as mock:
        response = logged_in_client(user, access_token=None).get(URL, {"q": "john.doe@example.org"})
        assert not mock.calls

    assert [found["id"] for found in response.json()] == [str(john.id)]


def test_an_expired_token_without_refresh_token_falls_back(user):
    """An expired token that can't be refreshed doesn't log the user out."""
    john = factories.UserFactory(email="john.doe@example.org")

    with responses.RequestsMock() as mock:
        response = logged_in_client(user, expires_in=-60).get(URL, {"q": "john.doe@example.org"})
        assert not mock.calls

    assert response.status_code == 200
    assert [found["id"] for found in response.json()] == [str(john.id)]


@responses.activate
def test_people_already_in_the_item_are_left_out(user):
    """item_id leaves out the Drive users who already have an access."""
    felix = factories.UserFactory(email="felix@example.org")
    item = factories.ItemFactory()
    factories.UserItemAccessFactory(item=item, user=felix)
    responses.add(
        responses.GET,
        SEARCH_URL,
        json={"results": [card("Félix", "felix@example.org"), card("Marie", "marie@example.org")]},
    )

    response = logged_in_client(user).get(URL, {"q": "m", "item_id": str(item.id)})

    assert [found["email"] for found in response.json()] == ["marie@example.org"]


def test_anonymous_users_are_refused():
    """Still only for logged-in users."""
    assert APIClient().get(URL, {"q": "mar"}).status_code == 401


def test_other_users_endpoints_keep_the_local_search(user):
    """users/contacts/ doesn't call Contacts."""
    with responses.RequestsMock() as mock:
        assert logged_in_client(user).get(f"{URL}contacts/").status_code == 200
        assert not mock.calls
    assert models.User.objects.count() == 1
