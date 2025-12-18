from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "users" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "telegram_id" BIGINT NOT NULL UNIQUE,
    "username" VARCHAR(255),
    "first_name" VARCHAR(255),
    "xp" INT NOT NULL DEFAULT 0,
    "level" INT NOT NULL DEFAULT 1,
    "streak_days" INT NOT NULL DEFAULT 0,
    "streak_last_date" DATE,
    "reminder_morning" VARCHAR(5) NOT NULL DEFAULT '09:00',
    "reminder_evening" VARCHAR(5) NOT NULL DEFAULT '21:00',
    "timezone_offset" INT NOT NULL DEFAULT 3,
    "reminders_enabled" BOOL NOT NULL DEFAULT True,
    "next_morning_reminder_at" TIMESTAMPTZ,
    "next_evening_reminder_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS "idx_users_telegra_ab91e9" ON "users" ("telegram_id");
COMMENT ON TABLE "users" IS 'Пользователь бота.';
CREATE TABLE IF NOT EXISTS "daily_logs" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "date" DATE NOT NULL,
    "energy_level" INT,
    "mood_text" VARCHAR(100),
    "assigned_step_ids" JSONB NOT NULL,
    "completed_step_ids" JSONB NOT NULL,
    "skip_reasons" JSONB NOT NULL,
    "day_rating" VARCHAR(20),
    "xp_earned" INT NOT NULL DEFAULT 0,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_daily_logs_user_id_4614a1" UNIQUE ("user_id", "date")
);
COMMENT ON TABLE "daily_logs" IS 'Дневник дня.';
CREATE TABLE IF NOT EXISTS "goals" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "title" VARCHAR(255) NOT NULL,
    "description" TEXT,
    "start_date" DATE NOT NULL,
    "deadline" DATE NOT NULL,
    "status" VARCHAR(20) NOT NULL DEFAULT 'active',
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "goals" IS 'Цель пользователя.';
CREATE TABLE IF NOT EXISTS "stages" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "title" VARCHAR(255) NOT NULL,
    "order" INT NOT NULL DEFAULT 0,
    "start_date" DATE NOT NULL,
    "end_date" DATE NOT NULL,
    "progress" INT NOT NULL DEFAULT 0,
    "status" VARCHAR(20) NOT NULL DEFAULT 'pending',
    "goal_id" INT NOT NULL REFERENCES "goals" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "stages" IS 'Этап цели (2-4 этапа на цель).';
CREATE TABLE IF NOT EXISTS "steps" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "title" VARCHAR(500) NOT NULL,
    "difficulty" VARCHAR(10) NOT NULL DEFAULT 'medium',
    "estimated_minutes" INT NOT NULL DEFAULT 15,
    "xp_reward" INT NOT NULL DEFAULT 20,
    "scheduled_date" DATE,
    "status" VARCHAR(20) NOT NULL DEFAULT 'pending',
    "completed_at" TIMESTAMPTZ,
    "stage_id" INT NOT NULL REFERENCES "stages" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "steps" IS 'Конкретный шаг/задача.';
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
    "lE"
)
