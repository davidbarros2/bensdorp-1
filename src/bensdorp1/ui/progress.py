"""Feedback-threshold context managers per rule 6.20 and the block-character
progress bar per rule 6.30 (D-03). Live rendering uses Rich.Live with a
dynamically-updated Group. time.monotonic() is the time source; tests mock it.
"""

import time
import types
from collections.abc import Iterator
from contextlib import contextmanager

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.progress import ProgressColumn, Task
from rich.spinner import Spinner
from rich.text import Text

from bensdorp1.ui.styles import _console as _default_console

# ---------------------------------------------------------------------------
# Threshold constants (rule 6.20)
# ---------------------------------------------------------------------------

THRESHOLD_SPINNER: float = 1.0  # seconds — below this: silent
THRESHOLD_PROGRESS: float = 6.0  # seconds — below this: spinner only
THRESHOLD_ETA: float = 30.0  # seconds — below this: progress bar; above: bar + ETA


# ---------------------------------------------------------------------------
# BlockBarColumn — spec-required block characters (rule 6.30)
# Rich's built-in BarColumn uses ━/╸/╺; spec requires █ and ░ ONLY.
# ---------------------------------------------------------------------------


class BlockBarColumn(ProgressColumn):
    """Progress bar column using spec-required full block and light shade characters.

    Rule 6.30 explicitly allows U+2588 (full block) and U+2591 (light shade) as
    exceptions to the no-unicode-icons rule. Never uses box-drawing bar chars.
    """

    def __init__(self, bar_width: int = 20) -> None:
        self.bar_width = bar_width
        super().__init__()

    def render(self, task: Task) -> Text:
        """Render the bar using █ for filled and ░ for empty slots."""
        pct = (task.completed / task.total) if task.total else 0.0
        filled = int(self.bar_width * pct)
        empty = self.bar_width - filled
        return Text("█" * filled + "░" * empty)


# ---------------------------------------------------------------------------
# SpinnerContext — unknown-duration operations (D-03, rule 6.22)
# ---------------------------------------------------------------------------


class SpinnerContext:
    """Context manager for unknown-duration operations.

    Silent if the operation completes in under THRESHOLD_SPINNER seconds.
    Shows a braille dots spinner (rule 6.22) once elapsed >= THRESHOLD_SPINNER.
    Callers may call tick() from inside the context to refresh the display.
    """

    def __init__(
        self,
        description: str,
        *,
        console: Console | None = None,
    ) -> None:
        self._description = description
        self._console: Console = console if console is not None else _default_console
        self._live: Live | None = None
        self._start: float = 0.0

    def __enter__(self) -> "SpinnerContext":
        self._start = time.monotonic()
        self._live = Live(
            Text(""),
            console=self._console,
            refresh_per_second=10,
            transient=True,
        )
        self._live.__enter__()
        return self

    def tick(self) -> None:
        """Refresh the spinner display based on elapsed time.

        Silent (empty Text) below THRESHOLD_SPINNER; braille spinner at or above.
        Callers invoke this from tight loops to animate the spinner.
        """
        if self._live is None:
            return
        elapsed = time.monotonic() - self._start
        if elapsed < THRESHOLD_SPINNER:
            renderable: RenderableType = Text("")
        else:
            renderable = Spinner("dots", self._description)
        self._live.update(renderable)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        if self._live is not None:
            self._live.__exit__(exc_type, exc_val, exc_tb)


# ---------------------------------------------------------------------------
# TrackContext — countable items with 4-tier feedback (D-03, rules 6.20/6.21)
# ---------------------------------------------------------------------------


class TrackContext:
    """Context manager for operations with a known item count.

    Four tiers based on elapsed time (rule 6.20):
      - <1s  (THRESHOLD_SPINNER):  silent
      - 1–6s (THRESHOLD_PROGRESS): braille spinner
      - 6–30s (THRESHOLD_ETA):     progress bar (no ETA)
      - >30s:                       progress bar + ETA

    advance(current_label) is called once per completed item.
    """

    def __init__(
        self,
        description: str,
        total: int,
        *,
        console: Console | None = None,
    ) -> None:
        self._description = description
        self._total = total
        self._console: Console = console if console is not None else _default_console
        self._live: Live | None = None
        self._start: float = 0.0
        self._completed: int = 0
        self._current_label: str = ""

    def advance(self, current_label: str = "") -> None:
        """Increment the completed count and refresh the display.

        Args:
            current_label: Label for the item just processed (e.g., a stock symbol).
        """
        self._completed += 1
        self._current_label = current_label
        elapsed = time.monotonic() - self._start
        if self._live is not None:
            self._live.update(self._build_renderable(elapsed))

    def _build_renderable(self, elapsed: float) -> RenderableType:
        """Select and build the tier-appropriate renderable for elapsed time."""
        if elapsed < THRESHOLD_SPINNER:
            return Text("")  # silent tier
        if elapsed < THRESHOLD_PROGRESS:
            return Spinner("dots", self._description)  # spinner tier
        if elapsed < THRESHOLD_ETA:
            return self._build_progress_block(elapsed, with_eta=False)
        return self._build_progress_block(elapsed, with_eta=True)

    def _build_progress_block(self, elapsed: float, *, with_eta: bool) -> Group:
        """Build the key:value progress display (rule 6.21).

        Keys: Progress, Current, Elapsed, [Remaining if with_eta].
        Values align at position determined by the longest key ('Remaining' = 9 chars).
        """
        pct = self._completed / self._total if self._total else 0.0
        filled = int(20 * pct)
        empty = 20 - filled
        bar = "█" * filled + "░" * empty

        pct_int = int(pct * 100)
        lines: list[Text] = [
            Text(
                f"Progress:   {bar}  {self._completed}/{self._total}  ({pct_int}%)"
            ),
            Text(f"Current:    {self._current_label}"),
            Text(f"Elapsed:    {self._format_duration(elapsed)}"),
        ]
        if with_eta:
            remaining = self._estimate_remaining(elapsed)
            lines.append(Text(f"Remaining:  ~{self._format_duration(remaining)}"))

        return Group(*lines)

    def _format_duration(self, seconds: float) -> str:
        """Format elapsed/remaining seconds as a human-readable string.

        Returns 'Xs' for under 60 seconds, 'Xm Ys' for 60 seconds and above.
        """
        total_secs = int(seconds)
        if total_secs < 60:
            return f"{total_secs}s"
        minutes = total_secs // 60
        secs = total_secs % 60
        return f"{minutes}m {secs}s"

    def _estimate_remaining(self, elapsed: float) -> float:
        """Estimate remaining seconds based on current completion rate."""
        if self._completed == 0 or elapsed <= 0:
            return 0.0
        rate = self._completed / elapsed
        remaining_items = self._total - self._completed
        return remaining_items / rate if rate > 0 else 0.0

    def __enter__(self) -> "TrackContext":
        self._start = time.monotonic()
        self._live = Live(
            Text(""),
            console=self._console,
            refresh_per_second=10,
            transient=True,
        )
        self._live.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        if self._live is not None:
            self._live.__exit__(exc_type, exc_val, exc_tb)


# ---------------------------------------------------------------------------
# MultiStepContext — multi-phase wrapper (D-03, rule 6.23)
# ---------------------------------------------------------------------------


class MultiStepContext:
    """Context manager for multi-phase operations.

    Tracks N total phases. Each phase is accessed via step(), which yields
    either a SpinnerContext (no total given) or a TrackContext (total given).

    After each phase exits, a persistent done line is printed per rule 6.23:
      [N/TOTAL] description... done.

    This line is printed AFTER the Live context exits (transient=True causes
    the Live display to disappear; the done line replaces it persistently).
    """

    def __init__(
        self,
        total: int,
        *,
        console: Console | None = None,
    ) -> None:
        self._total = total
        self._console: Console = console if console is not None else _default_console
        self._current: int = 0

    def __enter__(self) -> "MultiStepContext":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        pass

    @contextmanager
    def step(
        self,
        description: str,
        total: int | None = None,
    ) -> Iterator[SpinnerContext | TrackContext]:
        """Context manager for one phase of a multi-step operation.

        Args:
            description: Phase label displayed in the header and done line.
            total:       Number of items to process, or None for an unknown-duration op.

        Yields:
            SpinnerContext (total is None) or TrackContext (total provided).
        """
        self._current += 1
        self._console.print(
            Text(f"[{self._current}/{self._total}] {description}")
        )

        inner: SpinnerContext | TrackContext
        if total is None:
            inner = SpinnerContext(description, console=self._console)
        else:
            inner = TrackContext(description, total, console=self._console)

        with inner:
            yield inner

        # After the Live context exits (transient=True), print the persistent done line
        # per rule 6.23: completed phases show "done." appended.
        self._console.print(
            Text(f"[{self._current}/{self._total}] {description}... done.")
        )


# ---------------------------------------------------------------------------
# _FeedbackNamespace — public D-03 API (re-exported as `feedback` in ui/__init__.py)
# ---------------------------------------------------------------------------


class _FeedbackNamespace:
    """Factory namespace matching the D-03 API.

    Provides feedback.spinner(), feedback.track(), and feedback.multi_step().
    """

    def spinner(
        self,
        description: str,
        *,
        console: Console | None = None,
    ) -> SpinnerContext:
        """Return a SpinnerContext for unknown-duration operations."""
        return SpinnerContext(description, console=console)

    def track(
        self,
        description: str,
        total: int,
        *,
        console: Console | None = None,
    ) -> TrackContext:
        """Return a TrackContext for countable-item operations."""
        return TrackContext(description, total, console=console)

    def multi_step(
        self,
        total: int,
        *,
        console: Console | None = None,
    ) -> MultiStepContext:
        """Return a MultiStepContext for multi-phase operations."""
        return MultiStepContext(total, console=console)


feedback: _FeedbackNamespace = _FeedbackNamespace()
