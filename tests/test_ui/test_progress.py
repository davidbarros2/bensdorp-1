"""Tests for ui/progress.py — spinner frames, 4 tiers via mocked time,
BlockBarColumn character assertions, multi-step done line (rule 6.23).

All tests run deterministically with no real sleep. time.monotonic is
monkeypatched to return controlled values where needed.
"""

from unittest.mock import MagicMock

import pytest
import rich.spinner
from rich.console import Console, Group
from rich.spinner import Spinner
from rich.text import Text

from bensdorp1.ui.progress import (
    BlockBarColumn,
    MultiStepContext,
    SpinnerContext,
    TrackContext,
    feedback,
)

# ---------------------------------------------------------------------------
# Spinner frame guard — protects against Rich version drift (rule 6.22)
# ---------------------------------------------------------------------------


def test_dots_spinner_frames_match_spec() -> None:
    """Rich 'dots' spinner must have exactly the 10-frame braille sequence.

    Rule 6.22 specifies: ⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏
    """
    expected = list("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
    # rich.spinner.SPINNERS is not in the public typed API; access via attribute
    spinners = getattr(rich.spinner, "SPINNERS")  # noqa: B009
    dots_data = spinners["dots"]
    frames = dots_data["frames"]
    assert list(frames) == expected


# ---------------------------------------------------------------------------
# BlockBarColumn character assertions (rule 6.30)
# ---------------------------------------------------------------------------


def test_block_bar_chars() -> None:
    """50% progress → 10 filled blocks and 10 empty blocks; no box-drawing chars."""
    column = BlockBarColumn(bar_width=20)
    task = MagicMock()
    task.completed = 10
    task.total = 20

    result = column.render(task)
    plain = result.plain

    assert plain.count("█") == 10
    assert plain.count("░") == 10
    assert "━" not in plain


def test_block_bar_chars_zero_total() -> None:
    """Zero total → all empty slots, no filled blocks."""
    column = BlockBarColumn(bar_width=20)
    task = MagicMock()
    task.completed = 0
    task.total = 0

    result = column.render(task)
    plain = result.plain

    assert plain.count("█") == 0
    assert plain.count("░") == 20


def test_block_bar_chars_full() -> None:
    """100% completion → all filled blocks, no empty slots."""
    column = BlockBarColumn(bar_width=20)
    task = MagicMock()
    task.completed = 20
    task.total = 20

    result = column.render(task)
    plain = result.plain

    assert plain.count("█") == 20
    assert plain.count("░") == 0


# ---------------------------------------------------------------------------
# TrackContext — 4 tier tests via direct _build_renderable() calls
# ---------------------------------------------------------------------------


def test_track_silent_fast() -> None:
    """elapsed=0.5s → silent tier: returns Text with plain==''."""
    ctx = TrackContext(
        "Fetching",
        100,
        console=Console(record=True, width=80),
    )
    result = ctx._build_renderable(0.5)
    assert isinstance(result, Text)
    assert result.plain == ""


def test_track_spinner_tier() -> None:
    """elapsed=3.0s → spinner tier: returns Spinner instance, NOT a Group."""
    ctx = TrackContext("Fetching", 100)
    result = ctx._build_renderable(3.0)
    assert isinstance(result, Spinner)
    assert not isinstance(result, Group)


def test_track_progress_tier() -> None:
    """elapsed=10.0s → progress-bar tier: Group with Progress/Current/Elapsed only."""
    ctx = TrackContext("Fetching", 100)
    ctx._completed = 25
    ctx._current_label = "AAPL"

    result = ctx._build_renderable(10.0)

    assert isinstance(result, Group)
    plains = [r.plain for r in result.renderables if isinstance(r, Text)]

    progress_lines = [p for p in plains if p.startswith("Progress:")]
    current_lines = [p for p in plains if p.startswith("Current:")]
    elapsed_lines = [p for p in plains if p.startswith("Elapsed:")]
    remaining_lines = [p for p in plains if p.startswith("Remaining:")]

    assert len(progress_lines) >= 1
    assert len(current_lines) >= 1
    assert len(elapsed_lines) >= 1
    assert len(remaining_lines) == 0


def test_track_eta_tier() -> None:
    """elapsed=45.0s → progress+ETA tier: Group contains Remaining line."""
    ctx = TrackContext("Fetching", 100)
    ctx._completed = 25
    ctx._current_label = "AAPL"

    result = ctx._build_renderable(45.0)

    assert isinstance(result, Group)
    plains = [r.plain for r in result.renderables if isinstance(r, Text)]
    remaining_lines = [p for p in plains if p.startswith("Remaining:")]
    assert len(remaining_lines) == 1


# ---------------------------------------------------------------------------
# SpinnerContext — silent below threshold, shows description above (rule 6.22)
# ---------------------------------------------------------------------------


def test_spinner_silent_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    """When elapsed < 1s, tick() renders empty Text (no braille frame chars)."""
    # Provide two time.monotonic values: start (0.0) and tick check (0.5)
    times = iter([0.0, 0.5])
    monkeypatch.setattr("bensdorp1.ui.progress.time.monotonic", lambda: next(times))

    con = Console(record=True, width=80)
    ctx = SpinnerContext("Loading", console=con)
    with ctx:
        ctx.tick()

    output = con.export_text()
    # No braille characters should appear (empty Text was rendered)
    braille_frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    for frame in braille_frames:
        assert frame not in output, f"Unexpected braille frame '{frame}' in output"


def test_spinner_shows_braille(monkeypatch: pytest.MonkeyPatch) -> None:
    """When elapsed >= 1s on tick, spinner description becomes renderable."""
    # start=0.0, then tick check at 2.0 (above THRESHOLD_SPINNER)
    times = iter([0.0, 2.0])
    monkeypatch.setattr("bensdorp1.ui.progress.time.monotonic", lambda: next(times))

    con = Console(record=True, width=80, force_terminal=True)
    ctx = SpinnerContext("TestOperation", console=con)
    with ctx:
        ctx.tick()

    output = con.export_text()
    # The description should be associated with the Spinner renderable.
    # We assert the description text appears in the output (spinner was activated).
    assert "TestOperation" in output


# ---------------------------------------------------------------------------
# TrackContext — advance() increments state (monkeypatch not needed here)
# ---------------------------------------------------------------------------


def test_track_advance_increments(monkeypatch: pytest.MonkeyPatch) -> None:
    """advance() increments _completed and updates _current_label."""
    # Provide stable monotonic values: enter, advance 1, advance 2
    times = iter([0.0, 0.1, 0.2, 0.3])
    monkeypatch.setattr("bensdorp1.ui.progress.time.monotonic", lambda: next(times))

    con = Console(record=True, width=80)
    ctx = TrackContext("Test", 10, console=con)
    with ctx:
        ctx.advance("AAPL")
        ctx.advance("GOOGL")

    assert ctx._completed == 2
    assert ctx._current_label == "GOOGL"


# ---------------------------------------------------------------------------
# MultiStepContext — done line persistence (rule 6.23)
# ---------------------------------------------------------------------------


def test_multi_step_done_line() -> None:
    """Each completed step prints '[N/TOTAL] description... done.' after Live exits."""
    con = Console(record=True, width=80)
    ctx = MultiStepContext(total=2, console=con)
    with ctx:
        with ctx.step("Fetch data"):
            pass
        with ctx.step("Save data"):
            pass

    output = con.export_text()
    assert "[1/2] Fetch data... done." in output
    assert "[2/2] Save data... done." in output


# ---------------------------------------------------------------------------
# feedback namespace — factory methods return correct types (D-03)
# ---------------------------------------------------------------------------


def test_feedback_namespace_factories() -> None:
    """feedback.spinner/track/multi_step return the correct context manager types."""
    spinner_ctx = feedback.spinner("x")
    assert isinstance(spinner_ctx, SpinnerContext)

    track_ctx = feedback.track("x", 10)
    assert isinstance(track_ctx, TrackContext)

    multi_ctx = feedback.multi_step(2)
    assert isinstance(multi_ctx, MultiStepContext)
