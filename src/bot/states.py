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


class QuizStates(StatesGroup):
    """Квиз перед онбордингом."""

    answering = State()  # Проход вопросов
    finished = State()  # Финальный экран


class MorningStates(StatesGroup):
    """Утренний ритуал."""

    waiting_for_energy = State()  # Ожидание оценки энергии (1-10)
    waiting_for_mood = State()  # Ожидание описания состояния
    showing_steps = State()  # Показ шагов на день
    waiting_for_quick_step = State()  # Ожидание выбора микрошага на 2 мин


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
    """Вечерний отчёт."""

    marking_done = State()  # Отметка что сделано
    waiting_for_skip_reason = State()  # Причина пропуска
    rating_day = State()  # Оценка дня


class OnboardingSprintStates(StatesGroup):
    """Мини-спринт после квиза."""

    paywall = State()  # Пейволл после микрошага


class GoalStates(StatesGroup):
    """Создание новой цели (после онбординга)."""

    waiting_for_goal = State()
    waiting_for_deadline = State()
    confirming_stages = State()
