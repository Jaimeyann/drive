"""User search backends and the result they return."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UserSearchResult:
    """One person to suggest.

    ``user`` is set when the address belongs to a Drive user: sharing with
    them creates an access. Without it, sharing sends an invitation to
    ``email``.
    """

    email: str
    full_name: str = ""
    user: Any = None
