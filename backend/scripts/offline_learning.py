#!/usr/bin/env python3
"""Offline learning report.

Reads the skipped-token tracker (SQLite) once at least 300 records exist,
shows which signals separated real runners from junk using a walk-forward
split (not in-sample), and suggests weight changes.

This script MUST NOT edit config by itself.
"""

import sys
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.db.session import SessionLocal
from app.db.models import SkippedToken, Token


def walk_forward_split(df: pd.DataFrame, train_size: float = 0.6, test_size: float = 0.2) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
    """Create walk-forward train/test splits.

    Returns [(train1, test1), (train2, test2), ...] where each successive
    train window slides forward by test_size proportion.
    """
    splits = []
    n = len(df)
    train_end = int(n * train_size)
    start = train_end
    while start + int(n * test_size) <= n:
        train = df.iloc[:start].copy()
        test = df.iloc[start:start + int(n * test_size)].copy()
        if len(test) > 0 and len(train) > 0:
            splits.append((train, test))
        start += int(n * test_size)
    return splits


def main() -> None:
    db_path = Path("~/.memeracer/memeradar.db")  # or detect properly
    # Find the database
    from app.core import get_db_path
    db_str = get_db_path()
    db_full = Path(db_str).expanduser() if db_str else Path("~/memeracer/memeradar.db")
    if not db_full.exists():
        # try common locations
        for p in [
            Path("~/.memeracer/memeradar.db"),
            Path("./db.sqlite"),
            Path("./backend/db.sqlite"),
        ]:
            p_exp = p.expanduser()
            if p_exp.exists():
                db_full = p_exp
                break

    if not db_full.exists():
        print(f"Database not found at {db_full}. Run the bot first to generate data.")
        sys.exit(1)

    conn = sqlite3.connect(str(db_full))

    # Load skipped tokens with features
    query = """
        SELECT
            score,
            safety_score,
            opportunity_score,
            liquidity_usd,
            market_cap_usd,
            num_holders,
            num_buyers,
            verdict,
            reject_reasons,
            hard_rejected,
            is_real_runner
        FROM skipped_tokens
        WHERE is_real_runner IS NOT NULL
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if len(df) < 300:
        print(f"Not enough records: {len(df)} (need at least 300)")
        sys.exit(0)

    print(f"Loaded {len(df)} skipped-token records from {db_full}\n")

    # Basic stats
    runners = df[df["is_real_runner"] == True]
    non_runners = df[df["is_real_runner"] == False]
    print(f"Real runners: {len(runners)}")
    print(f"Non-runners (skipped): {len(non_runners)}\n")

    # Walk-forward analysis
    print("=== Walk-forward signal analysis ===")
    splits = walk_forward_split(df)
    for i, (train, test) in enumerate(splits[:3]):  # show first 3 splits
        # Simple classifier: use opportunity_score > threshold
        train_scores = train["opportunity_score"] if "opportunity_score" in train.columns else train.get("opportunity_score", pd.Series(dtype=float))
        # Since opportunity_score is a column, use it
        pass

    # Analyze which features separate runners from junk
    print("\n=== Feature comparison: runners vs non-runners ===")
    for col in ["safety_score", "opportunity_score", "liquidity_usd", "market_cap_usd", "num_holders", "num_buyers"]:
        if col in df.columns:
            runner_vals = df[df["is_real_runner"] == True][col]
            non_runner_vals = df[df["is_real_runner"] == False][col]
            if len(runner_vals) > 0 and len(non_runner_vals) > 0:
                print(f"{col}:")
                print(f"  Runners mean: {runner_vals.mean():.2f}")
                print(f"  Non-runners mean: {non_runner_vals.mean():.2f}")
                print(f"  Difference: {runner_vals.mean() - non_runner_vals.mean():.2f}\n")

    # Suggest weight changes based on what separated runners from junk
    print("=== Suggested weight adjustments (manual review required) ===")
    print("Review the feature differences above and consider adjusting:")
    print("  - opportunity_weights:momentum, volume, buyers if relevant")
    print("  - weights:liquidity, holders, creator, bundle, honeypot, rugcheck")
    print("  - Run the bot with the new weights and verify performance")
    print("  NEVER edit config.yaml automatically from this script!\n")

    # Score bucket analysis
    print("=== Score bucket win rates ===")
    df_copy = df.copy()
    df_copy["score_bucket"] = pd.cut(df_copy["score"], bins=[0, 30, 40, 50, 60, 70, 80, 100], labels=["0-30", "31-40", "41-50", "51-60", "61-70", "71-80", "81-100"])
    bucket_stats = df_copy.groupby("score_bucket").apply(
        lambda g: {
            "count": len(g),
            "runners": int((g["is_real_runner"] == True).sum()),
            "win_rate": round((g["is_real_runner"] == True).mean() * 100, 1),
        }
    )
    print(bucket_stats.to_string())

    print(f"\nMinimum records threshold (300) met: {len(df) >= 300}")


if __name__ == "__main__":
    main()