"""Canonical, domain-neutral email address validation for API boundaries."""

import re

_LOCAL = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
_EMAIL = re.compile(rf"(?=.{{3,320}}$)(?=.{{1,64}}@){_LOCAL}@(?>{_LABEL}\.)+[A-Za-z]{{2,63}}")


def normalize_email(value: object) -> str | None:
    """Trim and lowercase a practical RFC 5322 dot-atom email, or return None."""
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    if not candidate or any(ord(char) < 32 for char in candidate):
        return None
    return candidate if _EMAIL.fullmatch(candidate) else None
