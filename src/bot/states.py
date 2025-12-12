"""
FSM States для Antipanic Bot.

Основные потоки:
- Onboarding: создание первой цели
- AntipanicSession: утренний ритуал (энергия → микродействия)
- Stuck: когда застрял
- Evening: вечерний отчёт

AICODE-NOTE: Упрощено для Этапа 1.3 TMA миграции.
Удалены неиспользуемые states: QuizStates, GoalStates.
"""

from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    """
    Онбординг: постановка первой цели.

    AICODE-NOTE: Упрощено для Этапа 1.2 TMA миграции.
    Убрано состояние confirming_stages - теперь цель создаётся сразу.
    """

    waiting_for_goal = State()  # Ожидание описания цели
    waiting_for_deadline = State()  # Ожидание дедлайна


class AntipanicSession(StatesGroup):
    """Антипараличный поток /morning: быстро в действие."""

    selecting_topic = State()  # Выбор цели/темы если их несколько
    rating_tension_before = State()  # Замер напряжения 0-10 перед действием
    doing_body_action = State()  # Телесное микро-действие
    doing_micro_action = State()  # Шаг по задаче 2-5 минут
    rating_tension_after = State()  # Замер после действий
    offered_deepen = State()  # Предложение углубиться или завершить


class StuckStates(StatesGroup):
    """Когда застрял."""

    waiting_for_blocker = State()  # Выбор что мешает
    waiting_for_details = State()  # Детали (если выбрал "не знаю с чего")
    showing_microhit = State()  # Показ микро-удара
    waiting_for_feedback_details = State()  # Детали после кнопки "Другое"


class EveningStates(StatesGroup):
    """
    Вечерний отчёт (упрощённый).

    AICODE-NOTE: Упрощено для Этапа 1.4 TMA миграции.
    Удалено состояние rating_day - теперь день завершается сразу без оценки.
    """

    marking_done = State()  # Отметка что сделано
    waiting_for_skip_reason = State()  # Причина пропуска


class OnboardingSprintStates(StatesGroup):
    """Мини-спринт после квиза."""

    paywall = State()  # Пейволл после микрошага
