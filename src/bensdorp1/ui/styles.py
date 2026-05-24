"""Style constants, console singleton, pure formatters, and kv-alignment helper.

Depends on: bensdorp1.config (MARKET_TZ, USER_TZ)
Used by: all ui/ modules and commands (via ui/__init__.py)
"""

from datetime import UTC, date, datetime

from rich.console import Console
from rich.style import Style

from bensdorp1.config import MARKET_TZ, USER_TZ

# ---------------------------------------------------------------------------
# Module-level console singleton (D-06)
# Auto-detects TTY, respects NO_COLOR env var.
# Tests pass Console(record=True) via console= parameter; never mutate this.
# ---------------------------------------------------------------------------

_console: Console = Console()

# ---------------------------------------------------------------------------
# Color palette — rule 6.29
# No bold, italic, or underline anywhere (rule 6.31)
# ---------------------------------------------------------------------------

ERROR_STYLE: Style = Style(color="red")
WARNING_STYLE: Style = Style(color="yellow")
INFO_STYLE: Style = Style(color="cyan")
SUCCESS_STYLE: Style = Style(color="green")
MUTED_STYLE: Style = Style(color="bright_black")


# ---------------------------------------------------------------------------
# Numerical formatters — rule 6.10
# ---------------------------------------------------------------------------


def format_price(value: float) -> str:
    """Format a USD price: $X,XXX.XX (rule 6.10)."""
    return f"${value:,.2f}"


def format_pct(value: float) -> str:
    """Format a percentage with explicit sign: +/-X.X% (rule 6.10)."""
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"


def format_pnl(value: float) -> str:
    """Format P&L with explicit sign and dollar symbol: +/-$X,XXX.XX (rule 6.10)."""
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):,.2f}"


def format_volume(value: int) -> str:
    """Format share volume with comma separators: X,XXX,XXX (rule 6.10)."""
    return f"{value:,}"


def format_days(n: int) -> str:
    """Format days held: '1 day' singular, 'N days' plural (rule 6.10)."""
    return f"{n} day" if n == 1 else f"{n} days"


# ---------------------------------------------------------------------------
# Date/time formatters — rules 6.24/6.25
# ---------------------------------------------------------------------------


def format_date(d: date) -> str:
    """Format a date as ISO 8601: YYYY-MM-DD (rule 6.24)."""
    return d.strftime("%Y-%m-%d")


def format_time(dt: datetime) -> str:
    """Format a datetime as HH:MM (24-hour, no TZ conversion) (rule 6.25)."""
    return dt.strftime("%H:%M")


# ---------------------------------------------------------------------------
# Timezone formatter — rule 6.26
# ---------------------------------------------------------------------------


def format_timezone_pair(dt: datetime) -> str:
    """Format a datetime as 'HH:MM ET (HH:MM City)' (rule 6.26).

    Market label is always literal 'ET' — NOT derived from MARKET_TZ.key.
    User label is city name from USER_TZ.key (e.g. 'Lisbon', 'Chicago').
    """
    et = dt.astimezone(MARKET_TZ)
    local = dt.astimezone(USER_TZ)
    city = USER_TZ.key.split("/")[-1]
    return f"{et:%H:%M} ET ({local:%H:%M} {city})"


# ---------------------------------------------------------------------------
# Relative duration formatter — rule 6.27
# ---------------------------------------------------------------------------


def format_relative_duration(
    dt: datetime,
    *,
    _now: datetime | None = None,
) -> str:
    """Return human-relative duration string per rule 6.27.

    _now is a test-only injection point; defaults to datetime.now(UTC).
    Bracket boundaries:
      <1 min  -> 'just now'
      1-59m   -> 'N minutes ago'
      1-23h   -> 'N hours ago'
      1-30d   -> 'N days ago'
      1-11mo  -> 'N months ago'
      >=12mo  -> 'N years ago'
    """
    now = _now if _now is not None else datetime.now(tz=UTC)
    delta = now - dt.astimezone(UTC)
    total_seconds = int(delta.total_seconds())
    minutes = total_seconds // 60
    hours = total_seconds // 3600
    days = total_seconds // 86400
    months = days // 30
    years = days // 365

    if total_seconds < 60:
        return "just now"
    if minutes < 60:
        return f"{minutes} minutes ago"
    if hours < 24:
        return f"{hours} hours ago"
    if days <= 30:
        return f"{days} days ago"
    if months < 12:
        return f"{months} months ago"
    return f"{years} years ago"


# ---------------------------------------------------------------------------
# KV alignment helper — rule 6.4
# ---------------------------------------------------------------------------


def _render_kv_block(
    data: dict[str, str],
    console: Console,
    indent: str = "",
) -> None:
    """Render key:value pairs aligned per rule 6.4.

    Values align at column max_key_len + 1 (colon) + 2 (spaces).
    Empty data guard prevents ValueError from max() on empty sequence.
    Markup is disabled (markup=False, highlight=False) to prevent Rich markup
    injection from untrusted caller-supplied dict values (T-05-04).
    """
    if not data:
        return
    max_key_len = max(len(k) for k in data)
    for k, v in data.items():
        spaces = (max_key_len - len(k)) + 2
        console.print(f"{indent}{k}:{' ' * spaces}{v}", markup=False, highlight=False)
