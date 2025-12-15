"""
Callback Data Factories для Antipanic Bot.

Все callback_data должны использовать эти фабрики.
НЕ ИСПОЛЬЗУЙ raw строки типа "energy:5" — только CallbackData subclasses.

Примеры использования:
    # В клавиатуре
    builder.button(
        text="5",
        callback_data=EnergyCallback(value=5)
    )

    # В хендлере
    @router.callback_query(EnergyCallback.filter(F.value >= 7))
    async def high_energy(cb: CallbackQuery, callback_data: EnergyCallback):
        energy = callback_data.value
"""

from enum import Enum

from aiogram.filters.callback_data import CallbackData

# === Enums ===


class BlockerType(str, Enum):
    """Типы блокеров (причины застревания)."""

    fear = "fear"  # 😨 Страшно
    unclear = "unclear"  # 🤷 Не знаю с чего начать
    no_time = "no_time"  # ⏰ Нет времени
    no_energy = "no_energy"  # 😴 Нет сил


class StepAction(str, Enum):
    """Действия с шагом."""

    done = "done"  # Выполнил
    skip = "skip"  # Пропустить
    stuck = "stuck"  # Застрял


class MicrohitFeedbackAction(str, Enum):
    """Реакция на микро-удар."""

    do = "do"  # Сделаю
    more = "more"  # Нужна ещё подсказка
    other = "other"  # Другое


class QuickStepAction(str, Enum):
    """Действия для кнопки быстрого микрошага."""

    quick = "quick"  # Шаг на 2 минуты
    keep = "keep"  # Оставить как есть


class EnergyLevel(str, Enum):
    """Упрощённые уровни энергии (3 вместо 10)."""

    low = "low"  # 😴 Мало сил (1-3)
    medium = "medium"  # 😐 Норм (4-6)
    high = "high"  # ⚡ Бодрый (7-10)


class DeepenAction(str, Enum):
    """Решение после анти-паралич шага."""

    more = "more"  # Хочу ещё 15-30 минут
    finish = "finish"  # Хватит на сегодня


class QuizAction(str, Enum):
    """Действия после квиза."""

    proceed = "proceed"  # Поехали в мини-спринт
    later = "later"  # Не сейчас


class PaywallAction(str, Enum):
    """Действия на пейволле после мини-спринта."""

    accept = "accept"
    decline = "decline"


class GoalManageAction(str, Enum):
    """Действия управления целями."""

    edit_stages = "edit_stages"  # Редактировать этапы
    delete = "delete"  # Удалить цель
    complete = "complete"  # Завершить цель
    pause = "pause"  # Приостановить
    resume = "resume"  # Возобновить


class StageManageAction(str, Enum):
    """Действия с этапами."""

    edit = "edit"  # Редактировать название
    delete = "delete"  # Удалить этап
    add = "add"  # Добавить новый этап


# === Callback Data Classes ===


class EnergyCallback(CallbackData, prefix="energy"):
    """
    Выбор уровня энергии (1-10) — legacy, для совместимости.

    Использование:
        EnergyCallback(value=7)
        EnergyCallback.filter(F.value >= 5)
    """

    value: int


class SimpleEnergyCallback(CallbackData, prefix="nrg"):
    """
    Упрощённый выбор энергии (3 уровня).
    Уменьшает когнитивную нагрузку по Hick's Law.

    Использование:
        SimpleEnergyCallback(level=EnergyLevel.low)
    """

    level: EnergyLevel


class BlockerCallback(CallbackData, prefix="blocker"):
    """
    Выбор причины застревания.

    Использование:
        BlockerCallback(type=BlockerType.fear)
        BlockerCallback.filter(F.type == BlockerType.unclear)
    """

    type: BlockerType


class StepCallback(CallbackData, prefix="step"):
    """
    Действие с конкретным шагом.

    Использование:
        StepCallback(action=StepAction.done, step_id=123)
        StepCallback.filter(F.action == StepAction.done)
    """

    action: StepAction
    step_id: int


class MicrohitFeedbackCallback(CallbackData, prefix="microhit"):
    """
    Обратная связь после микро-удара.

    Использование:
        MicrohitFeedbackCallback(action=MicrohitFeedbackAction.do, step_id=1, blocker=BlockerType.fear)

    step_id=0 означает "без привязки к шагу".
    """

    action: MicrohitFeedbackAction
    step_id: int  # 0 = без привязки к шагу
    blocker: BlockerType


class MicrohitOptionCallback(CallbackData, prefix="mhopt"):
    """
    Выбор конкретного варианта микро-удара из списка.

    Используется в Stage 2.3 для показа нескольких вариантов на выбор.

    Использование:
        MicrohitOptionCallback(index=1, blocker=BlockerType.fear, step_id=0)

    index: 1-based индекс выбранного варианта
    step_id=0 означает "без привязки к шагу".
    """

    index: int  # 1-based индекс варианта
    blocker: BlockerType
    step_id: int  # 0 = без привязки к шагу


class RatingCallback(CallbackData, prefix="rating"):
    """
    Оценка дня (1-5 или emoji).

    Использование:
        RatingCallback(value=4)
        RatingCallback.filter(F.value >= 3)
    """

    value: int


class QuickStepCallback(CallbackData, prefix="quickstep"):
    """
    Действие для быстрого микрошага на 2 минуты.

    Использование:
        QuickStepCallback(action=QuickStepAction.quick)
        QuickStepCallback.filter(F.action == QuickStepAction.quick)
    """

    action: QuickStepAction


class GoalSelectCallback(CallbackData, prefix="goalpick"):
    """Выбор активной цели в новом утреннем потоке."""

    goal_id: int


class TensionCallback(CallbackData, prefix="tension"):
    """Выбор уровня напряжения/тревоги 0-10."""

    value: int


class DeepenCallback(CallbackData, prefix="deepen"):
    """Решение углубиться после анти-паралич шага."""

    action: DeepenAction


class QuizAnswerCallback(CallbackData, prefix="quiz"):
    """Ответ на вопрос квиза."""

    question: int
    option: int


class QuizResultActionCallback(CallbackData, prefix="quizact"):
    """Действие на итоговом экране квиза."""

    action: QuizAction


class PaywallCallback(CallbackData, prefix="paywall"):
    """Действие на пейволле после микрошага."""

    action: PaywallAction


class GoalManageCallback(CallbackData, prefix="goalman"):
    """Управление конкретной целью."""

    action: GoalManageAction
    goal_id: int


class StageManageCallback(CallbackData, prefix="stageman"):
    """Управление конкретным этапом."""

    action: StageManageAction
    stage_id: int
    goal_id: int
