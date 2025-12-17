"""
Скрипт для пересчёта прогресса всех этапов.
Запуск: python -m src.scripts.recalc_progress
"""

import asyncio

from tortoise import Tortoise

from src.database.config import TORTOISE_ORM
from src.database.models import Stage, Step


async def recalculate_all_stages():
    """Пересчитывает прогресс для всех этапов."""
    await Tortoise.init(config=TORTOISE_ORM)

    stages = await Stage.all()
    print(f"Found {len(stages)} stages to recalculate")

    for stage in stages:
        # Получаем все шаги этапа
        all_steps = await Step.filter(stage_id=stage.id)
        total_count = len(all_steps)

        if total_count == 0:
            print(f"  Stage {stage.id} '{stage.title}': no steps, skipping")
            continue

        # Считаем выполненные шаги
        completed_count = sum(1 for s in all_steps if s.status == "completed")

        # Рассчитываем прогресс
        new_progress = int((completed_count / total_count) * 100)
        old_progress = stage.progress

        stage.progress = new_progress

        # Проверяем статус
        finished_count = sum(
            1 for s in all_steps if s.status in ("completed", "skipped")
        )
        if finished_count == total_count and completed_count > 0:
            stage.status = "completed"
        elif stage.status == "pending" and completed_count > 0:
            stage.status = "active"

        await stage.save()
        print(
            f"  Stage {stage.id} '{stage.title}': {old_progress}% -> {new_progress}% ({completed_count}/{total_count} completed)"
        )

    await Tortoise.close_connections()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(recalculate_all_stages())
