"""Create the sample DuckDB database used by examples/modular-data-ci.yml.

    python examples/make_sample_db.py            # healthy data, all checks pass
    python examples/make_sample_db.py --broken   # stale data and negative amounts

Timestamps are generated relative to the current time (UTC), so the freshness and
period-based checks pass right after the database is created.
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb

DEFAULT_PATH = Path(__file__).parent / "data" / "shop.duckdb"
DAYS = 14


def build(path: Path, *, now: datetime, broken: bool = False, seed: int = 42) -> int:
    """Write the database to ``path`` (replacing it) and return the number of orders."""
    rng = random.Random(seed)
    now_utc = now.astimezone(timezone.utc).replace(tzinfo=None)
    shift = timedelta(days=3) if broken else timedelta(0)  # broken: no orders for 3 days

    rows = []
    order_id = 1
    for day in range(DAYS):
        for _ in range(40 + day % 3):
            minutes = rng.randint(1, 24 * 60 - 1)
            created_at = now_utc - shift - timedelta(days=day, minutes=minutes)
            amount = round(rng.uniform(10, 60), 2)
            coupon = "SAVE10" if rng.random() < 0.1 else None
            rows.append((order_id, rng.randint(1, 300), amount, created_at, coupon))
            order_id += 1
    if broken:
        for index in (5, 50, 120):
            rows[index] = (*rows[index][:2], -abs(rows[index][2]), *rows[index][3:])

    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    with duckdb.connect(str(path)) as conn:
        conn.execute(
            """
            CREATE TABLE orders (
                order_id INTEGER NOT NULL,
                customer_id INTEGER NOT NULL,
                amount DOUBLE NOT NULL,
                created_at TIMESTAMP NOT NULL,
                coupon_code VARCHAR
            )
            """
        )
        conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--broken", action="store_true", help="inject data quality problems")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    count = build(args.path, now=datetime.now(timezone.utc), broken=args.broken, seed=args.seed)
    print(f"wrote {count} orders to {args.path}{' (broken)' if args.broken else ''}")


if __name__ == "__main__":
    main()
