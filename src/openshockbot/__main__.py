from __future__ import annotations

import logging

from dotenv import load_dotenv

from .bot import run_bot
from .config import ConfigurationError, Settings


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        settings = Settings.from_env()
    except ConfigurationError as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc
    run_bot(settings)


if __name__ == "__main__":
    main()
