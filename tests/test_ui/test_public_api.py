"""Public surface smoke tests for bensdorp1.ui.

Verifies:
- Every name in __all__ resolves (test_public_api_complete).
- Re-exports are by-reference identity with source modules
  (test_public_api_identity_with_source_modules).
- No ui/*.py file imports from disallowed subpackages — db/data/strategy/commands
  (test_no_disallowed_imports_in_ui).
- record_console fixture works for export_text() assertions
  (test_record_console_fixture_works).
"""

import ast
import types
from pathlib import Path

from rich.console import Console

import bensdorp1.ui
import bensdorp1.ui.empty_states
import bensdorp1.ui.messages
import bensdorp1.ui.progress
import bensdorp1.ui.prompts
import bensdorp1.ui.styles
import bensdorp1.ui.tables

# ---------------------------------------------------------------------------
# UI source directory — relative to worktree root, resolved at test time
# ---------------------------------------------------------------------------

_UI_DIR = Path(__file__).parent.parent.parent / "src" / "bensdorp1" / "ui"

# ---------------------------------------------------------------------------
# Disallowed top-level import prefixes per D-08
# ---------------------------------------------------------------------------

_DISALLOWED_PREFIXES = (
    "bensdorp1.db",
    "bensdorp1.data",
    "bensdorp1.strategy",
    "bensdorp1.commands",
)


def test_public_api_complete() -> None:
    """Every name in bensdorp1.ui.__all__ resolves and is not None."""
    assert hasattr(bensdorp1.ui, "__all__"), "bensdorp1.ui must define __all__"
    assert len(bensdorp1.ui.__all__) >= 25, (
        f"Expected >= 25 entries in __all__, got {len(bensdorp1.ui.__all__)}"
    )
    for name in bensdorp1.ui.__all__:
        obj = getattr(bensdorp1.ui, name, None)
        assert obj is not None, f"bensdorp1.ui.{name} resolved to None"


def test_public_api_identity_with_source_modules() -> None:
    """Re-exports are the same object as the source module export (identity).

    Verifies monkeypatching through either bensdorp1.ui or the source module
    works correctly — no aliasing or wrapping.
    """
    identity_pairs: list[tuple[str, types.ModuleType]] = [
        ("Severity", bensdorp1.ui.messages),
        ("render_table", bensdorp1.ui.tables),
        ("confirm_prompt", bensdorp1.ui.prompts),
        ("feedback", bensdorp1.ui.progress),
        ("format_price", bensdorp1.ui.styles),
        ("print_empty_state", bensdorp1.ui.empty_states),
        ("ERROR_STYLE", bensdorp1.ui.styles),
        ("INFO_STYLE", bensdorp1.ui.styles),
        ("MUTED_STYLE", bensdorp1.ui.styles),
        ("SUCCESS_STYLE", bensdorp1.ui.styles),
        ("WARNING_STYLE", bensdorp1.ui.styles),
        ("BlockBarColumn", bensdorp1.ui.progress),
        ("SpinnerContext", bensdorp1.ui.progress),
        ("TrackContext", bensdorp1.ui.progress),
        ("MultiStepContext", bensdorp1.ui.progress),
        ("THRESHOLD_ETA", bensdorp1.ui.progress),
        ("THRESHOLD_PROGRESS", bensdorp1.ui.progress),
        ("THRESHOLD_SPINNER", bensdorp1.ui.progress),
        ("print_error", bensdorp1.ui.messages),
        ("print_info", bensdorp1.ui.messages),
        ("print_message", bensdorp1.ui.messages),
        ("print_success", bensdorp1.ui.messages),
        ("print_warning", bensdorp1.ui.messages),
        ("number_prompt", bensdorp1.ui.prompts),
        ("text_prompt", bensdorp1.ui.prompts),
        ("format_date", bensdorp1.ui.styles),
        ("format_days", bensdorp1.ui.styles),
        ("format_pct", bensdorp1.ui.styles),
        ("format_pnl", bensdorp1.ui.styles),
        ("format_relative_duration", bensdorp1.ui.styles),
        ("format_time", bensdorp1.ui.styles),
        ("format_timezone_pair", bensdorp1.ui.styles),
        ("format_volume", bensdorp1.ui.styles),
    ]

    for public_name, source_module in identity_pairs:
        ui_obj = getattr(bensdorp1.ui, public_name, None)
        src_obj = getattr(source_module, public_name, None)
        assert ui_obj is src_obj, (
            f"bensdorp1.ui.{public_name} is not the same object as "
            f"{source_module.__name__}.{public_name} — "
            "re-export must be by reference"
        )


def test_no_disallowed_imports_in_ui() -> None:
    """No .py file in src/bensdorp1/ui/ imports from db/data/strategy/commands (D-08).

    Uses ast.parse to walk ImportFrom nodes — catches top-level and nested imports.
    """
    assert _UI_DIR.is_dir(), f"UI source directory not found: {_UI_DIR}"

    violations: list[str] = []
    for py_file in sorted(_UI_DIR.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                for prefix in _DISALLOWED_PREFIXES:
                    if node.module == prefix or node.module.startswith(prefix + "."):
                        rel = py_file.relative_to(_UI_DIR.parent.parent.parent)
                        violations.append(
                            f"{rel} line {node.lineno}: from {node.module} import ..."
                        )

    assert not violations, (
        "D-08 violation — ui/*.py must not import from "
        "db/data/strategy/commands:\n" + "\n".join(f"  {v}" for v in violations)
    )


def test_record_console_fixture_works(record_console: Console) -> None:
    """record_console fixture provides a working Console(record=True, width=80)."""
    record_console.print("hello")
    output = record_console.export_text()
    assert "hello" in output
