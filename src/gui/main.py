"""Launch the PsyMetriQ Flet workspace."""

import argparse
import logging
import os

import flet as ft

from src.gui.application import main


def run() -> None:
    """Launch desktop mode by default or a local browser preview on request."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--web",
        action="store_true",
        help="Serve the GUI in a local browser instead of opening a desktop window.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8550)
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default=os.environ.get("PSYMETRIQ_LOG_LEVEL", "INFO").upper(),
        help="GUI/backend log detail (default: INFO; DEBUG adds render diagnostics).",
    )
    arguments = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, arguments.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    logging.getLogger(__name__).info(
        "Launching Flet workspace view=%s host=%s port=%s",
        "web" if arguments.web else "desktop",
        arguments.host if arguments.web else "local",
        arguments.port if arguments.web else "auto",
    )
    ft.run(
        main,
        host=arguments.host if arguments.web else None,
        port=arguments.port if arguments.web else 0,
        view=ft.AppView.WEB_BROWSER if arguments.web else ft.AppView.FLET_APP,
    )


if __name__ == "__main__":
    run()
