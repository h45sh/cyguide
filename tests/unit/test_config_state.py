import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from cyguide.ui.screens.config_modal import KeyProfileManager

pytestmark = pytest.mark.fast


def test_key_profile_manager_add_and_active_defaults():
    """Verify adding profiles automatically handles IDs, naming, and active key pointers."""
    mgr = KeyProfileManager()
    assert mgr.cloud_keys == []
    assert mgr.active_key_id is None
    assert mgr.editing_profile_id is None

    # Adding first profile makes it both active and editing
    p1 = mgr.add_key_profile(name="Primary OpenAI", provider="openai", api_key="sk-test1")
    assert p1["id"] in mgr.active_key_id
    assert mgr.editing_profile_id == p1["id"]
    assert len(mgr.cloud_keys) == 1
    assert mgr.get_active_profile()["name"] == "Primary OpenAI"

    # Adding second profile shifts editing_profile_id but keeps active_key_id
    p2 = mgr.add_key_profile(name="Backup Groq", provider="groq", api_key="gsk-test2")
    assert mgr.active_key_id == p1["id"]
    assert mgr.editing_profile_id == p2["id"]
    assert len(mgr.cloud_keys) == 2


def test_key_profile_manager_deletion_fallback():
    """Verify deleting the active profile safely shifts active pointer to remaining profiles."""
    mgr = KeyProfileManager()
    p1 = mgr.add_key_profile(name="Key 1", api_key="key1")
    p2 = mgr.add_key_profile(name="Key 2", api_key="key2")
    p3 = mgr.add_key_profile(name="Key 3", api_key="key3")

    assert mgr.active_key_id == p1["id"]

    # Delete active key (Key 1) -> active should shift to Key 2
    deleted = mgr.delete_key_profile(p1["id"])
    assert deleted["id"] == p1["id"]
    assert len(mgr.cloud_keys) == 2
    assert mgr.active_key_id == p2["id"]

    # Delete remaining keys until empty
    mgr.delete_key_profile(p2["id"])
    assert mgr.active_key_id == p3["id"]

    mgr.delete_key_profile(p3["id"])
    assert mgr.cloud_keys == []
    assert mgr.active_key_id is None
    assert mgr.editing_profile_id is None
    assert mgr.get_active_profile() is None


def test_key_profile_manager_manual_activation():
    """Verify setting active key works and reflects in get_active_profile."""
    mgr = KeyProfileManager()
    p1 = mgr.add_key_profile(name="Key 1")
    p2 = mgr.add_key_profile(name="Key 2")

    assert mgr.active_key_id == p1["id"]
    mgr.set_active_key(p2["id"])
    assert mgr.active_key_id == p2["id"]
    assert mgr.get_active_profile()["name"] == "Key 2"


@given(
    st.lists(
        st.text(min_size=10, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_"),
        min_size=1,
        max_size=10,
        unique=True,
    )
)
def test_key_uniqueness_validation_invariant(keys):
    """Property: Real API keys are rejected if duplicated, while placeholders are exempt."""
    from cyguide.engine.explainer import is_placeholder_key

    real_keys = [k for k in keys if not is_placeholder_key(k)]
    if not real_keys:
        return

    mgr = KeyProfileManager()
    for i, k in enumerate(real_keys):
        mgr.add_key_profile(name=f"Key {i}", api_key=k)

    # All inserted real keys must be detected as non-unique when tested against other IDs
    for k in real_keys:
        assert mgr.validate_key_uniqueness(k, exclude_id="non_existent") is False
        # But valid when excluding the profile that owns it
        owner = next(p for p in mgr.cloud_keys if p["api_key"] == k)
        assert mgr.validate_key_uniqueness(k, exclude_id=owner["id"]) is True

    # Placeholders are exempt from duplicate collisions
    assert mgr.validate_key_uniqueness("sk-placeholder") is True
    assert mgr.validate_key_uniqueness("") is True

    # A fresh unique key must pass
    assert mgr.validate_key_uniqueness("sk-brand-new-completely-unique-key-12345") is True
