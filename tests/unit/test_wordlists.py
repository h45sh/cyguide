"""Unit tests for centralized wordlists, auto-seeding, and macro substitution."""

import os
from pathlib import Path

from cyguide import paths
from cyguide.engine.gateway import ActionGateway
from cyguide.engine.wordlists import (
    DEFAULT_WORDLIST_NAME,
    get_available_wordlists,
    resolve_wordlist,
    seed_bundled_wordlists,
    substitute_wordlist_macros,
)


def test_paths_wordlist_helpers(tmp_path):
    data_dir = str(tmp_path)
    w_dir = paths.get_default_wordlists_dir(data_dir=data_dir)
    assert os.path.isdir(w_dir)
    assert w_dir == str(tmp_path / "wordlists")

    p1 = paths.get_wordlist_path("common_dirs", data_dir=data_dir)
    assert p1.endswith("common_dirs.txt")

    p2 = paths.get_wordlist_path("custom.txt", data_dir=data_dir)
    assert p2.endswith("custom.txt")
    assert not p2.endswith("custom.txt.txt")


def test_seed_bundled_wordlists(tmp_path):
    w_dir = str(tmp_path / "wordlists")
    seeded = seed_bundled_wordlists(w_dir)

    assert len(seeded) >= 5
    expected_files = [
        "common_dirs.txt",
        "subdomains_500.txt",
        "common_params.txt",
        "common_passwords.txt",
        "common_usernames.txt",
    ]
    for ef in expected_files:
        fp = Path(w_dir) / ef
        assert fp.exists(), f"Expected {ef} to exist"
        assert fp.stat().st_size > 0, f"Expected {ef} to be non-empty"

    # Subsequent run without overwrite should not re-seed existing files
    second_run = seed_bundled_wordlists(w_dir, overwrite=False)
    assert len(second_run) == 0

    # Overwrite run should re-seed
    overwrite_run = seed_bundled_wordlists(w_dir, overwrite=True)
    assert len(overwrite_run) == len(seeded)


def test_get_available_wordlists_auto_seeds(tmp_path):
    w_dir = str(tmp_path / "auto_seed_wordlists")
    available = get_available_wordlists(w_dir)

    assert "common_dirs" in available
    assert "subdomains_500" in available
    assert "common_params" in available
    assert os.path.isfile(available["common_dirs"])


def test_resolve_wordlist(tmp_path):
    w_dir = str(tmp_path / "resolve_wordlists")

    # 1. Macro {wordlist} resolves to default common_dirs
    p_default = resolve_wordlist("{wordlist}", target_dir=w_dir)
    assert p_default.endswith(f"{DEFAULT_WORDLIST_NAME}.txt")
    assert os.path.isfile(p_default)

    # 2. Macro with argument {wordlist:subdomains_500}
    p_sub = resolve_wordlist("{wordlist:subdomains_500}", target_dir=w_dir)
    assert p_sub.endswith("subdomains_500.txt")
    assert os.path.isfile(p_sub)

    # 3. Direct identifier without macro syntax
    p_params = resolve_wordlist("common_params", target_dir=w_dir)
    assert p_params.endswith("common_params.txt")

    # 4. Direct existing file on disk
    custom_file = tmp_path / "my_custom_list.txt"
    custom_file.write_text("endpoint1\nendpoint2\n", encoding="utf-8")
    p_custom = resolve_wordlist(str(custom_file), target_dir=w_dir)
    assert p_custom == str(custom_file.resolve())


def test_substitute_wordlist_macros(tmp_path):
    w_dir = str(tmp_path / "subst_wordlists")

    # 1. Standard substitution
    cmd = "gobuster dir -u http://127.0.0.1 -w {wordlist}"
    res_cmd, resolved = substitute_wordlist_macros(cmd, target_dir=w_dir)
    assert "{wordlist}" not in res_cmd
    assert "common_dirs.txt" in res_cmd
    assert len(resolved) == 1

    # 2. Named substitution
    cmd_sub = "ffuf -u http://127.0.0.1 -w {wordlist:common_params}"
    res_sub, resolved_sub = substitute_wordlist_macros(cmd_sub, target_dir=w_dir)
    assert "{wordlist:common_params}" not in res_sub
    assert "common_params.txt" in res_sub
    assert len(resolved_sub) == 1

    # 3. User override
    user_override = str(tmp_path / "override.txt")
    Path(user_override).write_text("item1\nitem2\n", encoding="utf-8")
    res_ov, resolved_ov = substitute_wordlist_macros(
        cmd, user_override=user_override, target_dir=w_dir
    )
    assert user_override in res_ov
    assert resolved_ov[0] == user_override


def test_action_gateway_resolves_wordlist():
    vars_dict = ActionGateway.resolve_entity_variables()
    assert "WORDLIST" in vars_dict
    assert vars_dict["WORDLIST"].endswith("common_dirs.txt")
