"""
Data migration script: SQLite → PostgreSQL.

Usage:
    python scripts/migrate_data.py --sqlite-path db.sqlite3

Environment variables required:
    - POSTGRES_HOST
    - POSTGRES_PORT
    - POSTGRES_DB
    - POSTGRES_USER
    - POSTGRES_PASSWORD
"""

import argparse
import asyncio
import logging
import os

import asyncpg
from tortoise import Tortoise

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def migrate_data(sqlite_path: str, postgres_url: str):
    """Migrate all data from SQLite to PostgreSQL."""

    # Connect to SQLite (source)
    logger.info("Connecting to SQLite...")
    await Tortoise.init(
        db_url=f"sqlite://{sqlite_path}",
        modules={"models": ["src.database.models"]}
    )

    # Import models after Tortoise init
    from src.database.models import DailyLog, Goal, QuizResult, Stage, Step, User

    # Connect to PostgreSQL (target)
    logger.info("Connecting to PostgreSQL...")
    pg_conn = await asyncpg.connect(postgres_url)

    try:
        # Initialize PostgreSQL schema
        logger.info("Initializing PostgreSQL schema...")
        await Tortoise.close_connections()
        await Tortoise.init(
            db_url=postgres_url.replace("postgres://", "asyncpg://"),
            modules={"models": ["src.database.models", "aerich.models"]}
        )
        await Tortoise.generate_schemas()

        # Reconnect to SQLite to read data
        await Tortoise.close_connections()
        await Tortoise.init(
            db_url=f"sqlite://{sqlite_path}",
            modules={"models": ["src.database.models"]}
        )

        # Migrate Users
        logger.info("Migrating users...")
        users = await User.all()
        user_mapping = {}  # old_id -> new_id

        for user in users:
            pg_id = await pg_conn.fetchval(
                """
                INSERT INTO "user" (
                    telegram_id, username, first_name, xp, level,
                    streak_days, streak_last_date, reminder_morning,
                    reminder_evening, timezone_offset, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (telegram_id) DO UPDATE
                SET username = EXCLUDED.username
                RETURNING id
                """,
                user.telegram_id, user.username, user.first_name,
                user.xp, user.level, user.streak_days, user.streak_last_date,
                user.reminder_morning, user.reminder_evening,
                user.timezone_offset, user.created_at
            )
            user_mapping[user.id] = pg_id

        logger.info(f"Migrated {len(users)} users")

        # Migrate Goals
        logger.info("Migrating goals...")
        goals = await Goal.all()
        goal_mapping = {}  # old_id -> new_id

        for goal in goals:
            pg_id = await pg_conn.fetchval(
                """
                INSERT INTO goal (
                    user_id, title, description, start_date, deadline,
                    status, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                user_mapping[goal.user_id], goal.title, goal.description,
                goal.start_date, goal.deadline, goal.status, goal.created_at
            )
            goal_mapping[goal.id] = pg_id

        logger.info(f"Migrated {len(goals)} goals")

        # Migrate Stages
        logger.info("Migrating stages...")
        stages = await Stage.all()
        stage_mapping = {}  # old_id -> new_id

        for stage in stages:
            pg_id = await pg_conn.fetchval(
                """
                INSERT INTO stage (
                    goal_id, title, "order", start_date, end_date,
                    progress, status
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                goal_mapping[stage.goal_id], stage.title, stage.order,
                stage.start_date, stage.end_date, stage.progress, stage.status
            )
            stage_mapping[stage.id] = pg_id

        logger.info(f"Migrated {len(stages)} stages")

        # Migrate Steps
        logger.info("Migrating steps...")
        steps = await Step.all()

        for step in steps:
            await pg_conn.execute(
                """
                INSERT INTO step (
                    stage_id, title, difficulty, estimated_minutes,
                    xp_reward, scheduled_date, status, completed_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                stage_mapping[step.stage_id], step.title, step.difficulty,
                step.estimated_minutes, step.xp_reward, step.scheduled_date,
                step.status, step.completed_at
            )

        logger.info(f"Migrated {len(steps)} steps")

        # Migrate DailyLogs
        logger.info("Migrating daily logs...")
        logs = await DailyLog.all()

        for log in logs:
            await pg_conn.execute(
                """
                INSERT INTO dailylog (
                    user_id, date, energy_level, mood_text,
                    assigned_step_ids, completed_step_ids, skip_reasons,
                    day_rating, xp_earned, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (user_id, date) DO NOTHING
                """,
                user_mapping[log.user_id], log.date, log.energy_level,
                log.mood_text, log.assigned_step_ids, log.completed_step_ids,
                log.skip_reasons, log.day_rating, log.xp_earned, log.created_at
            )

        logger.info(f"Migrated {len(logs)} daily logs")

        # Migrate QuizResults
        logger.info("Migrating quiz results...")
        quiz_results = await QuizResult.all()

        for qr in quiz_results:
            await pg_conn.execute(
                """
                INSERT INTO quizresult (
                    user_id, answers, dependency_score, diagnosis, completed_at
                )
                VALUES ($1, $2, $3, $4, $5)
                """,
                user_mapping[qr.user_id], qr.answers, qr.dependency_score,
                qr.diagnosis, qr.completed_at
            )

        logger.info(f"Migrated {len(quiz_results)} quiz results")

        logger.info("Migration completed successfully!")

    finally:
        await pg_conn.close()
        await Tortoise.close_connections()


def main():
    parser = argparse.ArgumentParser(description="Migrate data from SQLite to PostgreSQL")
    parser.add_argument(
        "--sqlite-path",
        default="db.sqlite3",
        help="Path to SQLite database file"
    )
    args = parser.parse_args()

    # Build PostgreSQL URL from environment
    postgres_url = (
        f"postgres://{os.getenv('POSTGRES_USER', 'antipanic')}:"
        f"{os.getenv('POSTGRES_PASSWORD')}@"
        f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
        f"{os.getenv('POSTGRES_PORT', '5432')}/"
        f"{os.getenv('POSTGRES_DB', 'antipanic')}"
    )

    asyncio.run(migrate_data(args.sqlite_path, postgres_url))


if __name__ == "__main__":
    main()
