from bensdorp1._app import app  # re-export for entry point

# Import all command modules to trigger @app.command() decorations:
import bensdorp1.commands.audit  # noqa: F401
import bensdorp1.commands.buy  # noqa: F401
import bensdorp1.commands.cash  # noqa: F401
import bensdorp1.commands.config  # noqa: F401
import bensdorp1.commands.detail  # noqa: F401
import bensdorp1.commands.fix  # noqa: F401
import bensdorp1.commands.help  # noqa: F401
import bensdorp1.commands.history  # noqa: F401
import bensdorp1.commands.init  # noqa: F401
import bensdorp1.commands.last  # noqa: F401
import bensdorp1.commands.portfolio  # noqa: F401
import bensdorp1.commands.refresh  # noqa: F401
import bensdorp1.commands.restore  # noqa: F401
import bensdorp1.commands.scan  # noqa: F401
import bensdorp1.commands.sell  # noqa: F401
import bensdorp1.commands.status  # noqa: F401
import bensdorp1.commands.validate  # noqa: F401

__all__ = ["app"]
