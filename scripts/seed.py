"""One command to fill the database:

    python -m scripts.seed

Options:
    --source PATH        the Kaggle CSV (default: data/raw/WA_Fn-UseC_-HR-Employee-Attrition.csv)
    --count N            how many employees to create (default 300)
    --seed N             random seed; same seed = same data (default 42)
    --email-domain D     domain for work emails (default example.com)
    --reset --yes        delete ALL employee data first (asks you to add --yes)

Running it twice is safe: rows that already exist are skipped.
"""
import argparse
import sys
from pathlib import Path

from app.db.session import SessionLocal
from scripts import config
from scripts.generate import build_master_data
from scripts.hr_dataset import DatasetError, clean_hr_dataset, load_raw
from scripts.load import load_master_data, reset_all_tables


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m scripts.seed", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=config.DEFAULT_SOURCE)
    parser.add_argument("--count", type=int, default=config.DEFAULT_COUNT)
    parser.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    parser.add_argument("--email-domain", default=config.DEFAULT_EMAIL_DOMAIN)
    parser.add_argument("--reset", action="store_true", help="delete all employee data first")
    parser.add_argument("--yes", action="store_true", help="confirm --reset")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.count < 1:
        print("--count must be at least 1")
        return 2
    if args.reset and not args.yes:
        print("--reset deletes ALL employees, departments, roles, salaries and attendance.")
        print("Run again with --reset --yes if you are sure.")
        return 2

    # 1. read and clean
    try:
        clean, report = clean_hr_dataset(load_raw(args.source))
    except DatasetError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(f"Source: {args.source}")
    print("\n".join("  " + line for line in report.lines()))
    if args.count > len(clean):
        print(f"Only {len(clean)} clean rows exist, so {len(clean)} employees will be created.")

    # 2. generate (no database yet)
    data = build_master_data(
        clean, count=args.count, seed=args.seed, email_domain=args.email_domain
    )
    print(
        f"Generated {len(data.employees)} employees, {len(data.salaries)} salary rows, "
        f"{len(data.attendance)} attendance rows (seed {args.seed})."
    )

    # 3. load, all in ONE transaction: it all works or nothing is saved
    with SessionLocal() as session:
        try:
            if args.reset:
                reset_all_tables(session)
                print("Existing employee data deleted.")
            summary = load_master_data(session, data)
            session.commit()
        except Exception:
            session.rollback()
            raise
    print("Saved to the database:")
    print("\n".join("  " + line for line in summary.lines()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
