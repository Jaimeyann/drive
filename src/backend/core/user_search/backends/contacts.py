"""Search the user's contacts in La Suite Contacts.

Contacts serves ranked people suggestions to the other Suite apps
(``GET /external_api/v1.0/search/``, JSContact cards) and learns from shares
(``POST /external_api/v1.0/interactions/``). Both are called with the user's
own OIDC access token: Contacts must accept tokens issued to Drive (its
``OIDC_RS_ALLOWED_AUDIENCES``), and Drive's tokens must name Contacts in
their audience.
"""

import logging
from collections import defaultdict

import requests

from core import models

from ..exceptions import UserSearchUnavailableError
from . import UserSearchResult
from .base import BaseUserSearchBackend

logger = logging.getLogger(__name__)

SEARCH_PATH = "/external_api/v1.0/search/"
INTERACTIONS_PATH = "/external_api/v1.0/interactions/"
# Contacts takes at most 50 items per interactions call with a user token.
MAX_INTERACTION_ITEMS = 50


def preferred_email(card):
    """The card's preferred address (``pref: 1``), else its first one."""
    emails = [
        entry
        for entry in (card.get("emails") or {}).values()
        if isinstance(entry, dict) and entry.get("address")
    ]
    if not emails:
        return ""
    emails.sort(key=lambda entry: entry.get("pref", float("inf")))
    return emails[0]["address"].strip()


class ContactsUserSearchBackend(BaseUserSearchBackend):
    """The people in the user's contacts, ranked by Contacts.

    Parameters (``USER_SEARCH["PARAMETERS"]``):
        base_url: Contacts' address, e.g. ``https://contacts.example.org``
        timeout: Seconds to wait for Contacts (a keystroke shouldn't hang)
        fallback_to_local: Search Drive's own users when Contacts can't answer
        verify_ssl: Check Contacts' TLS certificate
    """

    requires_access_token = True
    # Contacts only searches the user's own address book: short queries
    # can't be used to list the instance's users.
    min_query_length = 1

    def __init__(self, base_url, timeout=2, fallback_to_local=True, verify_ssl=True):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.fallback_to_local = fallback_to_local
        self.verify_ssl = verify_ssl

    def _headers(self, access_token):
        return {"Authorization": f"Bearer {access_token}"}

    def search(self, user, query, *, limit, access_token=None):
        """Ask Contacts for the user's people, then match them to Drive users."""
        if not access_token:
            raise UserSearchUnavailableError("No access token to call Contacts with.")
        try:
            response = requests.get(
                f"{self.base_url}{SEARCH_PATH}",
                # Groups are left out: the share modal can't show them yet.
                params={"q": query, "kind": "individual", "limit": limit},
                headers=self._headers(access_token),
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
            response.raise_for_status()
            cards = response.json()["results"]
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            logger.warning("Contacts search failed: %s", exc)
            raise UserSearchUnavailableError(str(exc)) from exc

        people = {}
        for card in cards if isinstance(cards, list) else []:
            if not isinstance(card, dict):
                continue
            email = models.normalize_email(preferred_email(card))
            if email and email not in people:
                people[email] = (card.get("name") or {}).get("full") or ""
        people.pop(models.normalize_email(user.email or ""), None)
        return self._match_users(people)

    @staticmethod
    def _match_users(people):
        """Turn ``{email: name}`` into results, with the Drive user when there is one.

        An address of exactly one active user becomes that user (sharing
        creates an access). An address no account uses becomes an invitation.
        Any other address is left out: an invitation to it would be refused,
        and an access to an inactive or ambiguous account is meaningless.
        """
        accounts = defaultdict(list)
        for account in models.User.objects.filter(email__in=list(people)):
            accounts[account.email].append(account)

        results = []
        for email, name in people.items():
            matches = accounts.get(email, [])
            if not matches:
                results.append(UserSearchResult(email=email, full_name=name))
            elif len(matches) == 1 and matches[0].is_active:
                found = matches[0]
                results.append(
                    UserSearchResult(email=email, full_name=found.full_name or name, user=found)
                )
        return results

    def record_share(self, user, emails, *, access_token=None):
        """Report a share to Contacts, so these people rank higher next time."""
        if not access_token or not emails:
            return
        items = [{"email": email} for email in dict.fromkeys(emails) if email]
        for start in range(0, len(items), MAX_INTERACTION_ITEMS):
            try:
                response = requests.post(
                    f"{self.base_url}{INTERACTIONS_PATH}",
                    json={"kind": "share", "items": items[start : start + MAX_INTERACTION_ITEMS]},
                    headers=self._headers(access_token),
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                # The share itself succeeded: the ranking is a bonus.
                logger.warning("Reporting a share to Contacts failed: %s", exc)
                return
