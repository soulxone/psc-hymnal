#!/usr/bin/env python3
"""PSC Hymnal — local lyrics + audio projection for public-domain hymns."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _log_startup_error(exc: BaseException) -> Path | None:
    """Best-effort: persist the traceback so a non-technical operator can find it."""
    import traceback

    try:
        from hymnal.paths import user_data_root

        log_path = user_data_root() / "startup_error.log"
    except Exception:
        log_path = Path.home() / "psc_hymnal_startup_error.log"
    try:
        log_path.write_text(
            "PSC Hymnal failed to start.\n\n"
            + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            encoding="utf-8",
        )
        return log_path
    except Exception:
        return None


if __name__ == "__main__":
    try:
        from hymnal.app import main

        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as exc:  # last-resort handler for a windowed app
        path = _log_startup_error(exc)
        if sys.platform == "win32":
            try:
                import ctypes

                msg = f"{type(exc).__name__}: {exc}"
                if path:
                    msg += f"\n\nDetails written to:\n{path}"
                ctypes.windll.user32.MessageBoxW(
                    0, msg, "PSC Hymnal — startup error", 0x10
                )
            except Exception:
                pass
        raise
