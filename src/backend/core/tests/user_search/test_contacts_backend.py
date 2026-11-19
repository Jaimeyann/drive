"""The Contacts backend: the user's contacts, matched to Drive users."""

import pytest
import responses
from requests.exceptions import ConnectTimeout

from core import factories
from core.user_search.backends.contacts import ContactsUserSearchBackend, preferred_email
from core.user_search.exceptions import UserSearchUnavailableError

from .conftest import ACCESS_TOKEN, CONTACTS_URL, INTERACTIONS_URL, SEARCH_URL, card

pytestmark = pytest.mark.django_db


def _backend():
    return ContactsUserSearchBackend(base_url=CONTACTS_URL)


def _answer(*cards, status=200):
    responses.add(responses.GET, SEARCH_URL, json={"results": list(cards)}, status=status)


@responses.activate
def test_contacts_is_asked_for_individuals_with_the_users_token(user):
    """The search sends the query, the limit and the user's token."""
    _answer()

    _backend().search(user, "mar", limit=5, access_token=ACCESS_TOKEN)

    request = responses.calls[0].request
    assert request.headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"
    assert request.params == {"q": "mar", "kind": "individual", "limit": "5"}


@responses.activate
def test_known_addresses_become_users_and_others_invitations(user):
    """An address of a Drive user is that user; any other is an invitation."""
    felix = factories.UserFactory(email="felix@example.org", full_name="Félix M.")
    _answer(card("Félix Marchand", "felix@example.org"), card("Marie Curie", "marie@example.org"))

    results = _backend().search(user, "m", limit=5, access_token=ACCESS_TOKEN)

    assert [(result.email, result.full_name, result.user) for result in results] == [
        ("felix@example.org", "Félix M.", felix),
        ("marie@example.org", "Marie Curie", None),
    ]


@responses.activate
def test_the_order_of_contacts_is_kept(user):
    """Contacts ranks the people: their order is kept."""
    _answer(*(card(f"P{i}", f"p{i}@example.org") for i in range(3)))

    results = _backend().search(user, "p", limit=5, access_token=ACCESS_TOKEN)

    assert [result.email for result in results] == [
        "p0@example.org",
        "p1@example.org",
        "p2@example.org",
    ]


@responses.activate
def test_the_preferred_address_is_used(user):
    """The address with pref 1 is the one suggested."""
    _answer(card("Bob", "bob@home.example", "bob@work.example", pref=2))

    results = _backend().search(user, "bob", limit=5, access_token=ACCESS_TOKEN)

    assert [result.email for result in results] == ["bob@work.example"]


@responses.activate
def test_addresses_are_matched_like_drive_stores_them(user):
    """Case and spaces don't hide a Drive user."""
    felix = factories.UserFactory(email="felix@example.org")
    _answer(card("Félix", " Felix@Example.org "))

    results = _backend().search(user, "fe", limit=5, access_token=ACCESS_TOKEN)

    assert [result.user for result in results] == [felix]


@responses.activate
def test_inactive_or_shared_addresses_are_left_out(user, settings):
    """An inactive account or an address of several accounts can't be shared with."""
    settings.OIDC_ALLOW_DUPLICATE_EMAILS = True
    factories.UserFactory(email="gone@example.org", is_active=False)
    factories.UserFactory(email="twice@example.org")
    factories.UserFactory(email="twice@example.org")
    _answer(card("Gone", "gone@example.org"), card("Twice", "twice@example.org"))

    assert not _backend().search(user, "x", limit=5, access_token=ACCESS_TOKEN)


@responses.activate
def test_the_user_and_cards_without_address_are_left_out(user):
    """No sharing with yourself, nor with a card without address."""
    no_email = card("No mail")
    no_email["emails"] = {}
    _answer(card("Me", "Alice@example.org"), no_email, card("Bob", "bob@example.org"))

    results = _backend().search(user, "a", limit=5, access_token=ACCESS_TOKEN)

    assert [result.email for result in results] == ["bob@example.org"]


@pytest.mark.parametrize(
    "answer",
    [
        {"status": 401, "json": {"detail": "Invalid token"}},
        {"status": 503, "json": {}},
        {"status": 200, "body": "not json"},
        {"status": 200, "json": {"no": "results"}},
        {"body": ConnectTimeout("too slow")},
    ],
)
@responses.activate
def test_contacts_failures_make_the_backend_unavailable(user, answer):
    """Any failure says the backend can't answer, so Drive can fall back."""
    responses.add(responses.GET, SEARCH_URL, **answer)

    with pytest.raises(UserSearchUnavailableError):
        _backend().search(user, "mar", limit=5, access_token=ACCESS_TOKEN)


def test_without_token_the_backend_is_unavailable(user):
    """No token, no call."""
    with pytest.raises(UserSearchUnavailableError):
        _backend().search(user, "mar", limit=5, access_token=None)


@responses.activate
def test_a_share_is_reported_as_an_interaction(user):
    """record_share posts the shared addresses, once each."""
    responses.add(responses.POST, INTERACTIONS_URL, status=204)

    _backend().record_share(
        user, ["bob@example.org", "bob@example.org", "eve@example.org"], access_token=ACCESS_TOKEN
    )

    request = responses.calls[0].request
    assert request.headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"
    assert responses.calls[0].request.body == (
        b'{"kind": "share", "items": [{"email": "bob@example.org"}, {"email": "eve@example.org"}]}'
    )


@responses.activate
def test_a_large_share_is_reported_in_chunks_of_50(user):
    """Contacts takes 50 items per call with a user token."""
    responses.add(responses.POST, INTERACTIONS_URL, status=204)

    _backend().record_share(
        user, [f"p{i}@example.org" for i in range(120)], access_token=ACCESS_TOKEN
    )

    assert len(responses.calls) == 3


@responses.activate
def test_a_failed_report_is_ignored(user):
    """The share succeeded: a failing report doesn't raise."""
    responses.add(responses.POST, INTERACTIONS_URL, status=503)

    _backend().record_share(user, ["bob@example.org"], access_token=ACCESS_TOKEN)


def test_a_report_without_token_is_skipped(user):
    """No token, no call."""
    with responses.RequestsMock() as mock:
        _backend().record_share(user, ["bob@example.org"], access_token=None)
        assert not mock.calls


@pytest.mark.parametrize(
    ("emails", "expected"),
    [
        ({"e1": {"address": "a@x.org"}, "e2": {"address": "b@x.org", "pref": 1}}, "b@x.org"),
        ({"e1": {"address": "a@x.org"}}, "a@x.org"),
        ({}, ""),
        ({"e1": {"label": "no address"}}, ""),
    ],
)
def test_preferred_email(emails, expected):
    """The preferred address, else the first, else nothing."""
    assert preferred_email({"emails": emails}) == expected
