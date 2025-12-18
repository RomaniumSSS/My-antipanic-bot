from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        -- Add rate limiting columns to daily_logs table
        ALTER TABLE "daily_logs" ADD COLUMN IF NOT EXISTS "morning_calls_count" INT NOT NULL DEFAULT 0;
        ALTER TABLE "daily_logs" ADD COLUMN IF NOT EXISTS "stuck_calls_count" INT NOT NULL DEFAULT 0;
    """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        -- Remove rate limiting columns from daily_logs table
        ALTER TABLE "daily_logs" DROP COLUMN IF EXISTS "morning_calls_count";
        ALTER TABLE "daily_logs" DROP COLUMN IF EXISTS "stuck_calls_count";
    """

