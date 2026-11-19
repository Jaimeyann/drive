"""The user's OIDC access token, for backends that call another Suite app."""

import logging

from django.conf import settings

from lasuite.oidc_login.backends import get_oidc_refresh_token
from lasuite.oidc_login.middleware import RefreshOIDCAccessToken

logger = logging.getLogger(__name__)


def fresh_access_token(request):
    """The session's access token, refreshed if it expired; None if unusable.

    Unlike the ``refresh_oidc_access_token`` decorator, a token that can't be
    refreshed (no refresh token stored, refresh refused) gives None instead
    of a 401 "session expired": a search shouldn't log the user out, it
    falls back to another backend.

    *request* is a Django or DRF request (DRF's forwards the session, the
    user, the path and the method this needs).
    """
    if not settings.OIDC_STORE_ACCESS_TOKEN:
        return None
    refresher = RefreshOIDCAccessToken(get_response=lambda _request: None)
    if refresher.is_expired(request):
        if not get_oidc_refresh_token(request.session):
            logger.debug("Access token expired and no refresh token stored")
            return None
        if refresher.process_request(request) is not None:
            logger.info("Access token expired and could not be refreshed")
            return None
    return request.session.get("oidc_access_token")
