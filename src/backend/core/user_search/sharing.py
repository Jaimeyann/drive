"""Tell the user search backend about shares, so it can rank people."""

from django.db import transaction

from . import user_search


def report_share(request, emails):
    """Report that the requesting user shared with *emails*, once committed.

    Best effort: runs after the share is saved, never fails it. A backend
    that needs the access token is skipped when the session holds none
    (e.g. a request from another app with its own token).
    """
    emails = [email for email in emails if email]
    if not emails:
        return
    backend = user_search
    access_token = None
    if backend.requires_access_token:
        session = getattr(request, "session", None)
        access_token = session.get("oidc_access_token") if session is not None else None
        if not access_token:
            return
    user = request.user
    transaction.on_commit(lambda: backend.record_share(user, emails, access_token=access_token))
