# User search: suggest people from La Suite Contacts

The share modal suggests people as the user types (`GET /api/v1.0/users/?q=`).
Who it suggests depends on the user search backend (`USER_SEARCH` setting):

| Backend | Suggests | Query |
|---|---|---|
| `core.user_search.backends.local.LocalUserSearchBackend` (default) | Drive's active users, matched on their email | 5 characters at least |
| `core.user_search.backends.contacts.ContactsUserSearchBackend` | The user's contacts in [La Suite Contacts](https://github.com/suitenumerique/contacts), ranked by how often the user shares with them | 1 character |

The frontend doesn't change: it keeps calling Drive, which calls Contacts.

## How the Contacts backend works

- Drive calls Contacts' `GET /external_api/v1.0/search/` with the user's own
  OIDC access token (stored in the session at login).
- Each person comes back as one of two shapes:
  - an address that belongs to a Drive user comes back as that user:
    sharing creates an access;
  - any other address comes back as `{"id": email, "email": email, ...}`:
    the share modal turns it into an invitation.
  - An address of an inactive account, or of several accounts, is left out.
- Groups are not suggested yet: the share modal can't show them.
- After an access, an invitation or a batch share, Drive reports it to
  Contacts (`POST /external_api/v1.0/interactions/`, kind `share`), so these
  people rank higher next time. A failed report never fails the share.
- If Contacts can't answer (down, slow, token refused, no token), the search
  falls back to the local backend, so the share modal keeps working.

## Configure Drive

```shell
USER_SEARCH_BACKEND=core.user_search.backends.contacts.ContactsUserSearchBackend
USER_SEARCH_BACKEND_PARAMETERS={"base_url": "https://contacts.example.org", "timeout": 2}

# The user's access token is needed, and must be refreshed
OIDC_STORE_ACCESS_TOKEN=True
OIDC_STORE_REFRESH_TOKEN=True
OIDC_STORE_REFRESH_TOKEN_KEY=<key generated with bin/fernetkey>

# One request per keystroke (debounced): raise the burst rate
API_USERS_LIST_THROTTLE_RATE_BURST=120/minute
```

Parameters of the Contacts backend:

| Parameter | Default | |
|---|---|---|
| `base_url` | (required) | Contacts' address |
| `timeout` | `2` | Seconds to wait for Contacts |
| `fallback_to_local` | `true` | Search Drive's users when Contacts can't answer; `false` returns no results instead |
| `verify_ssl` | `true` | Check Contacts' TLS certificate |

## Configure Contacts and the identity provider

- Contacts must accept tokens issued to Drive: `drive` in Contacts'
  `OIDC_RS_ALLOWED_AUDIENCES`, and `share` in the kinds Drive may report
  (Contacts' default `EXTERNAL_API`).
- Drive's access tokens must name Contacts in their audience (in Keycloak, an
  audience mapper on the `drive` client with `contacts` as included client
  audience). Otherwise Contacts' token introspection answers "inactive" and
  Drive falls back to the local search.

## Local development

Drive and Contacts must trust the same identity provider. The simplest is to
log in to Drive through the Contacts dev realm, which has a `drive` client
with the audience mapper:

```shell
# env.d/development/common.local
OIDC_OP_JWKS_ENDPOINT=http://host.docker.internal:8975/realms/contacts/protocol/openid-connect/certs
OIDC_OP_AUTHORIZATION_ENDPOINT=http://localhost:8975/realms/contacts/protocol/openid-connect/auth
OIDC_OP_TOKEN_ENDPOINT=http://host.docker.internal:8975/realms/contacts/protocol/openid-connect/token
OIDC_OP_USER_ENDPOINT=http://host.docker.internal:8975/realms/contacts/protocol/openid-connect/userinfo
OIDC_OP_LOGOUT_ENDPOINT=http://localhost:8975/realms/contacts/protocol/openid-connect/logout
OIDC_RP_CLIENT_ID=drive
OIDC_RP_CLIENT_SECRET=ThisIsAnExampleKeyForDevPurposeOnly

USER_SEARCH_BACKEND=core.user_search.backends.contacts.ContactsUserSearchBackend
USER_SEARCH_BACKEND_PARAMETERS={"base_url": "http://host.docker.internal:8971"}
OIDC_STORE_ACCESS_TOKEN=True
OIDC_STORE_REFRESH_TOKEN=True
OIDC_STORE_REFRESH_TOKEN_KEY=<key generated with bin/fernetkey>
```

Log in to Drive as `user1` / `user1`: the share modal suggests `user1`'s
contacts from the Contacts demo data.
