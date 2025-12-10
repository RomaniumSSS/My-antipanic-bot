"""
FSM States для Antipanic Bot.

Основные потоки:
- Onboarding: создание первой цели
- Morning: утренний ритуал (энергия → шаги)
- Stuck: когда застрял
- Evening: вечерний отчёт
"""

from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    """Онбординг: постановка первой цели."""

    waiting_for_goal = State()  # Ожидание описания цели
    waiting_for_deadline = State()  # Ожидание дедлайна
    confirming_stages = State()  # Подтверждение этапов от LLM


class MorningStates(StatesGroup):
    """Утренний ритуал."""

    waiting_for_energy = State()  # Ожидание оценки энергии (1-10)
    waiting_for_mood = State()  # Ожидание описания состояния
    showing_steps = State()  # Показ шагов на день
    waiting_for_quick_step = State()  # Ожидание выбора микрошага на 2 мин


class StuckStates(StatesGroup):
    """Когда застрял."""

    waiting_for_blocker = State()  # Выбор что мешает
    waiting_for_details = State()  # Детали (если выбрал "не знаю с чего")
    showing_microhit = State()  # Показ микро-удара
    waiting_for_feedback_details = State()  # Детали после кнопки "Другое"


class EveningStates(StatesGroup):
    """Вечерний отчёт."""

    marking_done = State()  # Отметка что сделано
    waiting_for_skip_reason = State()  # Причина пропуска
    rating_day = State()  # Оценка дня


class GoalStates(StatesGroup):
    """Создание новой цели (после онбординга)."""

    waiting_for_goal = State()
    waiting_for_deadline = State()
    confirming_stages = State()
