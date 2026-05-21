from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from rules_labeling_backend.api import DEFAULT_DB_PATH, create_app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the rules labeling API.")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="DuckDB database path.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = create_app(args.db)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
