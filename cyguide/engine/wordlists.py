"""Centralized wordlist management, auto-seeding, and macro substitution.

Deep module encapsulating wordlist resolution, bundled asset extraction,
and dynamic template expansion for fuzzing and reconnaissance tools.
"""

import gzip
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from cyguide import paths

# Wordlists located in packaged assets directory (with fallback to repo root)
_PKG_WORDLISTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "wordlists"
_ROOT_WORDLISTS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "wordlists"
BUNDLED_WORDLISTS_DIR = _PKG_WORDLISTS_DIR if _PKG_WORDLISTS_DIR.exists() else _ROOT_WORDLISTS_DIR

# Matches {wordlist} or {wordlist:name}
WORDLIST_MACRO_REGEX = re.compile(r"\{wordlist(?::([a-zA-Z0-9_\-]+))?\}")

DEFAULT_WORDLIST_NAME = "common_dirs"


def seed_bundled_wordlists(target_dir: Optional[str] = None, overwrite: bool = False) -> List[str]:
    """Extract bundled starter wordlists into user's wordlists directory.

    Ensures the target directory exists with secure 0o700 permissions and
    wordlist files are written with 0o600 permissions. Automatically decompresses
    bundled .txt.gz archives or copies uncompressed .txt files.
    """
    dest_dir = Path(target_dir) if target_dir else Path(paths.get_default_wordlists_dir())
    dest_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    seeded: List[str] = []
    if not BUNDLED_WORDLISTS_DIR.exists():
        return seeded

    for src_file in sorted(BUNDLED_WORDLISTS_DIR.iterdir()):
        if src_file.name.endswith(".gz"):
            # Target filename without .gz (e.g. common_dirs.txt)
            dest_file = dest_dir / src_file.stem
            if overwrite or not dest_file.exists():
                with gzip.open(src_file, "rb") as f_in, open(dest_file, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                try:
                    dest_file.chmod(0o600)
                except OSError:
                    pass
                seeded.append(str(dest_file.resolve()))
        elif src_file.suffix == ".txt":
            dest_file = dest_dir / src_file.name
            if overwrite or not dest_file.exists():
                shutil.copy2(src_file, dest_file)
                try:
                    dest_file.chmod(0o600)
                except OSError:
                    pass
                seeded.append(str(dest_file.resolve()))

    return seeded


def get_available_wordlists(target_dir: Optional[str] = None) -> Dict[str, str]:
    """Return mapping of available wordlists {name: absolute_path}.

    Automatically seeds bundled wordlists if the target directory is empty.
    """
    dest_dir = Path(target_dir) if target_dir else Path(paths.get_default_wordlists_dir())
    dest_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    files = list(dest_dir.glob("*.txt"))
    if not files:
        seed_bundled_wordlists(str(dest_dir))
        files = list(dest_dir.glob("*.txt"))

    return {f.stem: str(f.resolve()) for f in sorted(files)}


def resolve_wordlist(
    name_or_macro: str,
    target_dir: Optional[str] = None,
) -> str:
    """Resolve a wordlist name, macro token, or direct file path to an absolute path.

    Supports:
      - Direct existing file path (e.g. "/tmp/custom.txt")
      - Named identifier (e.g. "common_dirs", "subdomains_500")
      - Macro tokens (e.g. "{wordlist:common_dirs}", "{wordlist}")
    """
    clean = name_or_macro.strip()

    # 1. Check if macro syntax: {wordlist:name} or {wordlist}
    match = WORDLIST_MACRO_REGEX.fullmatch(clean)
    if match:
        named_arg = match.group(1)
        name = named_arg if named_arg else DEFAULT_WORDLIST_NAME
    else:
        name = clean

    # 2. Check if clean is already a valid existing file on disk
    expanded_path = os.path.abspath(os.path.expanduser(name))
    if os.path.isfile(expanded_path):
        return expanded_path

    # 3. Lookup in centralized wordlists directory
    dest_dir = Path(target_dir) if target_dir else Path(paths.get_default_wordlists_dir())
    wordlist_map = get_available_wordlists(str(dest_dir))

    # Strip .txt if caller provided it
    lookup_key = name[:-4] if name.endswith(".txt") else name
    if lookup_key in wordlist_map:
        return wordlist_map[lookup_key]

    # 4. Fallback: try seeding bundled wordlists if not found
    seed_bundled_wordlists(str(dest_dir))
    refreshed_map = get_available_wordlists(str(dest_dir))
    if lookup_key in refreshed_map:
        return refreshed_map[lookup_key]

    # 5. Ultimate default fallback to common_dirs
    if DEFAULT_WORDLIST_NAME in refreshed_map:
        return refreshed_map[DEFAULT_WORDLIST_NAME]

    # Return standard default path even if not yet created
    return paths.get_wordlist_path(DEFAULT_WORDLIST_NAME, data_dir=str(dest_dir.parent))


def substitute_wordlist_macros(
    text: str,
    user_override: Optional[str] = None,
    target_dir: Optional[str] = None,
) -> Tuple[str, List[str]]:
    """Substitute {wordlist} and {wordlist:name} tokens in command/flag text.

    Args:
        text: Command or flag string containing macros.
        user_override: Optional user-supplied custom wordlist path overriding macros.
        target_dir: Optional target wordlist directory.

    Returns:
        Tuple of (substituted_text, list_of_resolved_file_paths).
    """
    resolved_paths: List[str] = []

    def _replace_macro(match: re.Match) -> str:
        if user_override and user_override.strip():
            resolved = resolve_wordlist(user_override.strip(), target_dir=target_dir)
        else:
            token = match.group(0)
            resolved = resolve_wordlist(token, target_dir=target_dir)
        resolved_paths.append(resolved)
        return resolved

    result_text = WORDLIST_MACRO_REGEX.sub(_replace_macro, text)
    return result_text, resolved_paths
