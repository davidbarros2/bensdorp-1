"""Public surface of the bensdorp1.ui subpackage.

All commands (Phases 6-14) consume only the names exported here — never
deep-import from ui.styles/messages/tables/prompts/progress/empty_states.
"""

from bensdorp1.ui.empty_states import print_empty_state
from bensdorp1.ui.messages import (
    Severity,
    print_error,
    print_info,
    print_message,
    print_success,
    print_warning,
)
from bensdorp1.ui.progress import (
    THRESHOLD_ETA,
    THRESHOLD_PROGRESS,
    THRESHOLD_SPINNER,
    BlockBarColumn,
    MultiStepContext,
    SpinnerContext,
    TrackContext,
    feedback,
)
from bensdorp1.ui.prompts import (
    confirm_prompt,
    number_prompt,
    text_prompt,
)
from bensdorp1.ui.styles import (
    ERROR_STYLE,
    INFO_STYLE,
    MUTED_STYLE,
    SUCCESS_STYLE,
    WARNING_STYLE,
    format_date,
    format_days,
    format_pct,
    format_pnl,
    format_price,
    format_relative_duration,
    format_time,
    format_timezone_pair,
    format_volume,
    render_kv_block,
)
from bensdorp1.ui.tables import render_table

__all__ = [
    "BlockBarColumn",
    "ERROR_STYLE",
    "INFO_STYLE",
    "MUTED_STYLE",
    "MultiStepContext",
    "Severity",
    "SUCCESS_STYLE",
    "SpinnerContext",
    "THRESHOLD_ETA",
    "THRESHOLD_PROGRESS",
    "THRESHOLD_SPINNER",
    "TrackContext",
    "WARNING_STYLE",
    "confirm_prompt",
    "feedback",
    "format_date",
    "format_days",
    "format_pct",
    "format_pnl",
    "format_price",
    "format_relative_duration",
    "format_time",
    "format_timezone_pair",
    "format_volume",
    "number_prompt",
    "print_empty_state",
    "print_error",
    "print_info",
    "print_message",
    "print_success",
    "print_warning",
    "render_kv_block",
    "render_table",
    "text_prompt",
]
