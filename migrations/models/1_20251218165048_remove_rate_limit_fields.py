from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "daily_logs" DROP COLUMN "morning_calls_count";
        ALTER TABLE "daily_logs" DROP COLUMN "stuck_calls_count";"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "daily_logs" ADD "morning_calls_count" INT NOT NULL DEFAULT 0;
        ALTER TABLE "daily_logs" ADD "stuck_calls_count" INT NOT NULL DEFAULT 0;"""


MODELS_STATE = (
    "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"
    "sq/vVO7MPN3adyorWBrbf7ws/wcy6Bem"
)
