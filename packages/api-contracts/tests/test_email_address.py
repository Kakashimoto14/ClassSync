import pytest
from classync_contracts.email_address import normalize_email


@pytest.mark.parametrize(
    "value,expected",
    [
        (" student.demo@gmail.com ", "student.demo@gmail.com"),
        ("Student.Demo+ClassSync@Example.EDU", "student.demo+classsync@example.edu"),
        ("juan.delacruz@student.pnm.edu.ph", "juan.delacruz@student.pnm.edu.ph"),
    ],
)
def test_email_normalization_accepts_valid_domains_and_canonicalizes(value, expected):
    assert normalize_email(value) == expected


@pytest.mark.parametrize(
    "value",
    ["", "user", "user@localhost", "user@@example.com", "first last@example.com",
     "a..b@example.com", ".a@example.com", "a@-example.com", "a@example..com"],
)
def test_email_normalization_rejects_malformed_addresses(value):
    assert normalize_email(value) is None
