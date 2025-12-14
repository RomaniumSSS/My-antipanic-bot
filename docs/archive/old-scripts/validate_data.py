"""
Validate data integrity before/after migration.

Usage:
    # Before migration (SQLite)
    python scripts/validate_data.py --db sqlite://db.sqlite3 --output pre_migration.json

    # After migration (PostgreSQL)
    python scripts/validate_data.py --db $DATABASE_URL --output post_migration.json

    # Compare
    python scripts/validate_data.py --compare pre_migration.json post_migration.json
"""

import argparse
import asyncio
import json
import logging

from tortoise import Tortoise

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_stats(db_url: str) -> dict:
    """Get database statistics."""
    await Tortoise.init(
        db_url=db_url,
        modules={"models": ["src.database.models"]}
    )

    from src.database.models import DailyLog, Goal, QuizResult, Stage, Step, User

    stats = {
        "users": await User.all().count(),
        "goals": await Goal.all().count(),
        "stages": await Stage.all().count(),
        "steps": await Step.all().count(),
        "daily_logs": await DailyLog.all().count(),
        "quiz_results": await QuizResult.all().count(),
        "goals_by_status": {},
        "stages_by_status": {},
        "steps_by_status": {},
    }

    # Count by status
    for status in ["active", "onboarding", "completed", "paused", "abandoned"]:
        count = await Goal.filter(status=status).count()
        if count > 0:
            stats["goals_by_status"][status] = count

    for status in ["pending", "active", "completed"]:
        count = await Stage.filter(status=status).count()
        if count > 0:
            stats["stages_by_status"][status] = count

        count = await Step.filter(status=status).count()
        if count > 0:
            stats["steps_by_status"][status] = count

    await Tortoise.close_connections()
    return stats


def compare_stats(pre: dict, post: dict) -> bool:
    """Compare pre and post migration stats."""
    logger.info("Comparing migration results...")

    all_match = True
    for key in pre:
        if pre[key] != post[key]:
            logger.error(f"MISMATCH in {key}: {pre[key]} != {post[key]}")
            all_match = False
        else:
            logger.info(f"✓ {key}: {pre[key]}")

    return all_match


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", help="Database URL")
    parser.add_argument("--output", help="Output JSON file")
    parser.add_argument("--compare", nargs=2, help="Compare two JSON files")

    args = parser.parse_args()

    if args.compare:
        with open(args.compare[0]) as f:
            pre = json.load(f)
        with open(args.compare[1]) as f:
            post = json.load(f)

        if compare_stats(pre, post):
            logger.info("✅ Migration validation PASSED")
        else:
            logger.error("❌ Migration validation FAILED")
            exit(1)

    elif args.db and args.output:
        stats = await get_stats(args.db)
        with open(args.output, 'w') as f:
            json.dump(stats, f, indent=2)
        logger.info(f"Stats saved to {args.output}")
        logger.info(json.dumps(stats, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
