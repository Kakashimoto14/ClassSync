import pytest

from scripts.postgres_restore_qualification import digest, restore_name


def test_fingerprint_canonicalizes_mapping_order_and_detects_changes():
    assert digest({"a": 1, "b": [2]}) == digest({"b": [2], "a": 1})
    assert digest({"a": 1, "b": [2]}) != digest({"a": 1, "b": [3]})


@pytest.mark.parametrize("name", ["postgres", "template0", "academic", "classsync_restore_123",
                                  "classsync_restore_" + "a" * 32 + "; DROP DATABASE postgres"])
def test_restore_refuses_original_or_nongenerated_database_names(name):
    with pytest.raises(ValueError):
        restore_name(name)


def test_restore_accepts_only_its_generated_namespace():
    name = "classsync_restore_" + "a" * 32
    assert restore_name(name) == name
