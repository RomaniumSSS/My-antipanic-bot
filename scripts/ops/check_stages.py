"""Проверка статуса этапов."""

import asyncio

from tortoise import Tortoise

from src.database.config import TORTOISE_ORM
from src.database.models import Stage


async def main():
    await Tortoise.init(config=TORTOISE_ORM)

    stages = await Stage.all().order_by("id")
    print("Current stages status:")
    print("-" * 60)
    for s in stages:
        print(f"Stage {s.id}: '{s.title}'")
        print(f"   status={s.status}, progress={s.progress}%")
    print("-" * 60)

    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
