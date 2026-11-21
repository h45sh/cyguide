"""Unit and workflow tests for preflight dependency, asset, and parameter verification."""

from typing import Optional

import pytest

from cyguide.engine.preflight import (
    PreflightVerifier,
)
from cyguide.ui.screens.preflight_modal import PreflightModal


class FakeToolAdapter:
    def __init__(self, name: str, is_installed: bool = True, binary: Optional[str] = None):
        self.name = name
        self._installed = is_installed
        self.binary = binary or name

    def validate_install(self) -> bool:
        return self._installed


class FakeRegistry:
    def __init__(self, tools: dict):
        self._tools = tools

    def get_tool(self, name: str):
        if name in self._tools:
            return {"adapter": self._tools[name], "manifest": None}
        return None


def test_preflight_missing_tool():
    verifier = PreflightVerifier()
    report = verifier.verify(tool_name="", target="127.0.0.1")
    assert not report.is_valid
    assert any(
        i.category == "binary" and "No security tool selected" in i.title for i in report.errors
    )


def test_preflight_binary_missing_provides_install_hint():
    fake_adapter = FakeToolAdapter("gobuster", is_installed=False)
    registry = FakeRegistry({"gobuster": fake_adapter})
    verifier = PreflightVerifier(registry=registry)

    report = verifier.verify(tool_name="gobuster", target="http://127.0.0.1:8888")
    assert not report.is_valid
    binary_errors = [i for i in report.errors if i.category == "binary"]
    assert len(binary_errors) == 1
    assert "gobuster" in binary_errors[0].title
    assert "apt install gobuster" in binary_errors[0].remediation_hint
    assert binary_errors[0].can_auto_remedy
    assert binary_errors[0].remedy_action == "copy_install_command"


def test_preflight_dnspython_always_valid():
    verifier = PreflightVerifier()
    report = verifier.verify(tool_name="dnspython", target="example.com")
    assert not any(i.category == "binary" for i in report.issues)


def test_preflight_empty_target_and_remedy():
    fake_adapter = FakeToolAdapter("nmap", is_installed=True)
    registry = FakeRegistry({"nmap": fake_adapter})
    verifier = PreflightVerifier(registry=registry)

    report = verifier.verify(tool_name="nmap", target="")
    assert not report.is_valid
    target_errors = [i for i in report.errors if i.category == "target"]
    assert len(target_errors) == 1
    assert target_errors[0].can_auto_remedy
    assert target_errors[0].remedy_action == "set_default_target"

    # Apply remedy
    new_target, new_flags, feedback = verifier.apply_remedy(
        target_errors[0], target="", flags="-sV"
    )
    assert new_target == "127.0.0.1"
    assert "127.0.0.1" in feedback


def test_preflight_unexpanded_placeholder_variable():
    verifier = PreflightVerifier()
    report = verifier.verify(tool_name="nmap", target="$TARGET")
    assert not report.is_valid
    assert any("Unexpanded variable placeholder" in i.title for i in report.errors)


def test_preflight_web_tool_missing_http_scheme():
    fake_adapter = FakeToolAdapter("gobuster", is_installed=True)
    registry = FakeRegistry({"gobuster": fake_adapter})
    verifier = PreflightVerifier(registry=registry)

    report = verifier.verify(tool_name="gobuster", target="192.168.1.100")
    assert not report.is_valid
    scheme_errors = [i for i in report.errors if i.category == "target"]
    assert len(scheme_errors) == 1
    assert "requires an HTTP/HTTPS URL" in scheme_errors[0].title
    assert scheme_errors[0].can_auto_remedy

    # Apply remedy
    new_target, _, feedback = verifier.apply_remedy(
        scheme_errors[0], target="192.168.1.100", flags=""
    )
    assert new_target == "http://192.168.1.100"
    assert "Updated target to" in feedback


def test_preflight_network_tool_with_url_warning():
    fake_adapter = FakeToolAdapter("nmap", is_installed=True)
    registry = FakeRegistry({"nmap": fake_adapter})
    verifier = PreflightVerifier(registry=registry)

    report = verifier.verify(tool_name="nmap", target="https://192.168.1.50:8443/login")
    assert report.is_valid  # Warnings are non-blocking
    assert report.has_warnings
    warns = [i for i in report.warnings if i.category == "target"]
    assert len(warns) == 1
    assert "expects a host or IP" in warns[0].title

    # Apply remedy
    new_target, _, feedback = verifier.apply_remedy(
        warns[0], target="https://192.168.1.50:8443/login", flags=""
    )
    assert new_target == "192.168.1.50"
    assert "Stripped URL scheme" in feedback


def test_preflight_sudo_ban_in_learning_mode():
    verifier = PreflightVerifier()
    report = verifier.verify(tool_name="nmap", target="127.0.0.1", flags="sudo -sS -Pn")
    assert not report.is_valid
    sec_errors = [i for i in report.errors if i.category == "security"]
    assert len(sec_errors) == 1
    assert "sudo" in sec_errors[0].title.lower()

    # Apply remedy
    _, new_flags, feedback = verifier.apply_remedy(
        sec_errors[0], target="127.0.0.1", flags="sudo -sS -Pn"
    )
    assert "sudo" not in new_flags
    assert new_flags == "-sS -Pn"


def test_preflight_ssrf_blocked_metadata_target():
    verifier = PreflightVerifier()
    report = verifier.verify(tool_name="nmap", target="169.254.169.254")
    assert not report.is_valid
    sec_errors = [i for i in report.errors if i.category == "security"]
    assert any("blocked by security policy" in i.title for i in sec_errors)


def test_preflight_missing_wordlist_and_seed_remedy(tmp_path):
    wordlists_dir = str(tmp_path / "wordlists")
    fake_adapter = FakeToolAdapter("gobuster", is_installed=True)
    registry = FakeRegistry({"gobuster": fake_adapter})
    verifier = PreflightVerifier(registry=registry, wordlists_dir=wordlists_dir)

    report = verifier.verify(
        tool_name="gobuster",
        target="http://127.0.0.1:8888",
        flags="dir -u http://127.0.0.1:8888 -w {wordlist:common_dirs}",
    )
    assert not report.is_valid
    wl_errors = [i for i in report.errors if i.category == "wordlist"]
    assert len(wl_errors) == 1
    assert wl_errors[0].remedy_action == "seed_wordlists"

    # Apply seeding remedy
    _, _, feedback = verifier.apply_remedy(
        wl_errors[0],
        target="http://127.0.0.1:8888",
        flags="dir -u http://127.0.0.1:8888 -w {wordlist:common_dirs}",
    )
    assert "starter wordlists" in feedback.lower()

    # Re-verify should now pass wordlist checks
    report2 = verifier.verify(
        tool_name="gobuster",
        target="http://127.0.0.1:8888",
        flags="dir -u http://127.0.0.1:8888 -w {wordlist:common_dirs}",
    )
    assert not any(i.category == "wordlist" for i in report2.errors)


def test_preflight_quick_check():
    assert PreflightVerifier.quick_check("nmap", "127.0.0.1", "sudo -sS") is not None
    assert PreflightVerifier.quick_check("nmap", "", "-sS") is not None
    assert PreflightVerifier.quick_check("nmap", "169.254.169.254", "-sS") is not None
    assert PreflightVerifier.quick_check("gobuster", "192.168.1.1", "dir") is not None
    assert PreflightVerifier.quick_check("nmap", "http://192.168.1.1", "-sV") is not None
    assert PreflightVerifier.quick_check("nmap", "192.168.1.1", "-sV") is None


@pytest.mark.asyncio
async def test_learning_session_preflight_integration(tmp_path):
    from unittest.mock import MagicMock

    from cyguide.engine.execution_session import ExecutionSession
    from cyguide.engine.learning import LearningSession
    from cyguide.engine.store import GraphStore

    store = GraphStore(":memory:")
    await store.initialize()
    fake_adapter = FakeToolAdapter("nmap", is_installed=True)
    registry = FakeRegistry({"nmap": fake_adapter})
    execution = ExecutionSession(store, MagicMock(), registry, MagicMock())

    session = LearningSession(store=store, registry=registry, execution=execution)
    session.active_tool = "nmap"

    # Preflight check with empty target
    report = session.verify_preflight(target="", flags="-sV")
    assert not report.is_valid
    assert len(report.errors) == 1

    # Apply remedy via session seam
    issue = report.errors[0]
    new_t, new_f, msg = session.apply_preflight_remedy(issue, target="", flags="-sV")
    assert new_t == "127.0.0.1"

    # Verify with updated target passes
    report_pass = session.verify_preflight(target=new_t, flags=new_f)
    assert report_pass.is_valid

    await store.close()


def test_preflight_modal_remedy_interaction():
    from unittest.mock import MagicMock

    from textual.app import App

    class DummyApp(App):
        pass

    app = DummyApp()
    fake_adapter = FakeToolAdapter("gobuster", is_installed=True)
    registry = FakeRegistry({"gobuster": fake_adapter})
    verifier = PreflightVerifier(registry=registry)

    # Report with missing scheme
    report = verifier.verify("gobuster", target="127.0.0.1", flags="dir")
    modal = PreflightModal(
        report=report,
        verifier=verifier,
        active_tool="gobuster",
        initial_target="127.0.0.1",
        initial_flags="dir",
    )
    modal._app = app
    modal._refresh_ui = MagicMock()

    assert not modal.report.is_valid
    # Trigger remedy for missing scheme
    modal._handle_remedy(0)
    assert modal.current_target == "http://127.0.0.1"
    assert modal.report.is_valid


def test_default_tool_targets_coverage_and_preflight():
    """Verify all 11 tools have valid default targets that satisfy preflight rules."""
    from cyguide.engine.preflight import DEFAULT_TOOL_TARGETS, get_tool_target_guidance
    from cyguide.engine.registry import ToolRegistry

    registry = ToolRegistry()
    registry.load_tools()
    verifier = PreflightVerifier()

    assert len(registry.tools) == 11
    for tool_name in registry.tools:
        assert tool_name in DEFAULT_TOOL_TARGETS
        target = DEFAULT_TOOL_TARGETS[tool_name]
        assert bool(target)

        report = verifier.verify(tool_name, target=target, flags="")
        # Target, security, and wordlist errors must be 0
        non_binary_errors = [
            i for i in report.issues if i.severity == "error" and i.category != "binary"
        ]
        assert not non_binary_errors, (
            f"Tool {tool_name} failed preflight on default target: {non_binary_errors}"
        )

        # Target guidance must exist and contain mandatory educational sections
        guidance = get_tool_target_guidance(tool_name)
        assert bool(guidance)
        assert "Target Scope" in guidance
        assert "Permissible & Effective Targets" in guidance
        assert "Strictly Prohibited & Dangerous Targets" in guidance
        assert "Operational Precautions & Ethics" in guidance


def test_all_tool_recipes_preflight_validity():
    """Verify every curriculum recipe in all tool manifests resolves and passes preflight."""
    from cyguide.engine.learning import RecipeBinding
    from cyguide.engine.preflight import DEFAULT_TOOL_TARGETS
    from cyguide.engine.registry import ToolRegistry

    registry = ToolRegistry()
    registry.load_tools()
    verifier = PreflightVerifier()

    for name, tool_entry in sorted(registry.tools.items()):
        manifest = tool_entry["manifest"]
        recipes = (
            manifest.learning.recipes if (manifest.learning and manifest.learning.recipes) else []
        )
        default_target = DEFAULT_TOOL_TARGETS[name]

        for idx, recipe in enumerate(recipes):
            resolved = RecipeBinding.resolve(
                manifest=manifest,
                target=default_target,
                flags_used=recipe.flags,
                recipe_idx=idx,
            )
            report = verifier.verify(name, target=default_target, flags=resolved.flags)
            non_binary_errors = [
                i for i in report.issues if i.severity == "error" and i.category != "binary"
            ]
            assert not non_binary_errors, (
                f"{name} recipe {idx} [{recipe.name}] failed preflight: {non_binary_errors}"
            )
