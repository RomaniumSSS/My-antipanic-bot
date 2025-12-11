from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "quiz_results" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            "answers" TEXT NOT NULL DEFAULT '[]',
            "dependency_score" DOUBLE PRECISION NOT NULL,
            "diagnosis" TEXT,
            "completed_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
        );
        """


async def downgrade(db: BaseDBAsyncClient) -> str:
    return 'DROP TABLE IF EXISTS "quiz_results";'
