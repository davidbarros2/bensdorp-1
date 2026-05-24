"""Env-resolved static configuration. Read at import time only (D-08)."""

import os
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_NAME: str = "bensdorp1"
MARKET_TZ: ZoneInfo = ZoneInfo("America/New_York")
USER_TZ: ZoneInfo = ZoneInfo(os.environ.get("BENSDORP1_USER_TZ", "Europe/Lisbon"))
DATA_DIR: Path = Path(os.environ.get("BENSDORP1_HOME", str(Path.home() / PROJECT_NAME)))
