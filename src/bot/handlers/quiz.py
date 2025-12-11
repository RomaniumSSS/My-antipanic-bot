"""Квиз перед созданием цели."""

import logging
from typing import Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.callbacks.data import (
    QuizAction,
    QuizAnswerCallback,
    QuizResultActionCallback,
)
from src.bot.keyboards import (
    main_menu_keyboard,
    quiz_question_keyboard,
    quiz_result_keyboard,
)
from src.bot.states import QuizStates
from src.database.models import QuizResult, User
from src.services.ai import ai_service

logger = logging.getLogger(__name__)

router = Router()


QUIZ_QUESTIONS: list[dict[str, Any]] = [
    {
        "number": 1,
        "title": "Недели пролетают, а ты всё ещё на старте?",
        "options": [("Да", 3), ("Скорее да", 2), ("Скорее нет", 1), ("Нет", 0)],
    },
    {
        "number": 2,
        "title": "Ты больше времени проводишь, планируя и думая о делах, чем реально их делая?",
        "options": [("Да", 3), ("Скорее да", 2), ("Скорее нет", 1), ("Нет", 0)],
    },
    {
        "number": 3,
        "title": 'Целый день можешь быть "занятым", но к вечеру понимаешь — ничего важного не сделал?',
        "options": [("Да", 3), ("Скорее да", 2), ("Скорее нет", 1), ("Нет", 0)],
    },
    {
        "number": 4,
        "title": "С каждым днём откладывания тревога становится всё сильнее?",
        "options": [("Да", 3), ("Скорее да", 2), ("Скорее нет", 1), ("Нет", 0)],
    },
    {
        "number": 5,
        "title": 'Сколько времени ты живёшь в режиме "завтра начну"?',
        "options": [
            ("Несколько дней", 1),
            ("Пару недель", 2),
            ("Месяц+", 3),
            ("Больше года", 4),
        ],
    },
    {
        "number": 6,
        "title": "Страшно открыть список дел, чтобы не увидеть весь завал?",
        "options": [("Да, избегаю", 3), ("Иногда", 2), ("Редко", 1), ("Нет", 0)],
    },
    {
        "number": 7,
        "title": "Чаще лежишь/залипаешь в экран, чем двигаешь хоть что-то важное?",
        "options": [("Постоянно", 3), ("Часто", 2), ("Иногда", 1), ("Редко", 0)],
    },
    {
        "number": 8,
        "title": "Каждый вечер стыдно за день, но завтра всё повторяется?",
        "options": [("Да, цикл", 3), ("Часто", 2), ("Иногда", 1), ("Редко", 0)],
    },
    {
        "number": 9,
        "title": "Ты уже пробовал to-do списки, трекеры привычек, мотивационные видео — но откат возвращается?",
        "options": [
            ("Да, много раз", 3),
            ("Пару раз", 2),
            ("Один раз", 1),
            ("Не пробовал", 0),
        ],
    },
    {
        "number": 10,
        "title": "Прямо сейчас есть хотя бы одна вещь, которую ты откладываешь уже несколько дней?",
        "options": [
            ("Да, и это меня душит", 4),
            ("Да, несколько", 3),
            ("Одна небольшая", 1),
            ("Нет", 0),
        ],
    },
]


async def _ask_question(
    message: Message | CallbackQuery, state: FSMContext, index: int
):
    question = QUIZ_QUESTIONS[index]
    text = f"Вопрос {index + 1}/10\n" f"{question['title']}"
    keyboard = quiz_question_keyboard(question["number"], question["options"])
    if isinstance(message, CallbackQuery):
        await message.message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


def calculate_quiz_score(answers: list[dict[str, Any]]) -> tuple[int, int]:
    """
    Подсчёт итогового балла квиза и отклонения от базового уровня.

    Returns:
        score: итоговый балл 0-100
        diff: отклонение от порогового значения 35 (floor at 0)
    """
    total_weight = sum(item.get("weight", 0) for item in answers)
    score = round((total_weight / 32) * 100)
    diff = max(0, int(round(score - 35)))
    return score, diff


async def start_quiz(message: Message, state: FSMContext, user: User) -> None:
    """Запуск квиза перед онбордингом."""
    await state.clear()
    await state.set_state(QuizStates.answering)
    await state.update_data(quiz_answers=[], quiz_index=0)

    await message.answer(
        "Перед стартом небольшой квиз — поймём, насколько держит паралич.",
    )
    await _ask_question(message, state, 0)


@router.message(Command("quiz"))
async def manual_quiz(message: Message, state: FSMContext) -> None:
    """Отладочный вход в квиз."""
    if not message.from_user:
        return
    user, _ = await User.get_or_create(
        telegram_id=message.from_user.id,
        defaults={
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
        },
    )
    await start_quiz(message, state, user)


@router.callback_query(QuizStates.answering, QuizAnswerCallback.filter())
async def handle_quiz_answer(
    callback: CallbackQuery, callback_data: QuizAnswerCallback, state: FSMContext
) -> None:
    """Обработка ответа на вопрос квиза."""
    await callback.answer()
    data = await state.get_data()
    current_index = data.get("quiz_index", 0)

    # Игнорируем если кликнули старый вопрос
    question = QUIZ_QUESTIONS[current_index]
    if question["number"] != callback_data.question:
        return

    selected_idx = callback_data.option
    try:
        answer_text, weight = question["options"][selected_idx]
    except IndexError:
        await callback.message.edit_text("Не понял ответ, попробуй ещё раз.")
        return

    answers = data.get("quiz_answers", [])
    answers.append(
        {
            "number": question["number"],
            "question": question["title"],
            "answer": answer_text,
            "weight": weight,
        }
    )
    next_index = current_index + 1

    if next_index < len(QUIZ_QUESTIONS):
        await state.update_data(quiz_answers=answers, quiz_index=next_index)
        await _ask_question(callback, state, next_index)
        return

    # Финал
    score, diff = calculate_quiz_score(answers)

    diagnosis = await ai_service.generate_quiz_diagnosis(answers, score)

    # Сохраняем результат
    if callback.from_user:
        user, _ = await User.get_or_create(
            telegram_id=callback.from_user.id,
            defaults={
                "username": callback.from_user.username,
                "first_name": callback.from_user.first_name,
            },
        )
        try:
            await QuizResult.create(
                user=user,
                answers=answers,
                dependency_score=score,
                diagnosis=diagnosis,
            )
        except Exception as err:  # noqa: BLE001
            logger.exception("Failed to save quiz result: %s", err)

    diff_line = f"Это на {diff}% выше среднего" if score > 35 else ""
    result_text = (
        f"⚠️ Твой уровень паралича: {score}/100\n"
        f"{diff_line}\n"
        f"{diagnosis}\n\n"
        'Если так оставить, ещё один год улетит так же — в "завтра" и чувство вины.\n'
        "Я не буду грузить тебя теориями.\n"
        "Моя задача — вытащить тебя в действие через микрошаги.\n"
        "Хочешь, давай попробуем буквально 5–10 минут действий — без обязательств?\n"
        "Я проведу тебя: 1 минута тело → 3 минуты микрошаг.\n"
        "Поехали?\n\n"
        "[Поехали] [Не сейчас]"
    )

    await state.set_state(QuizStates.finished)
    await state.update_data(
        onboarding_quiz_score=score, onboarding_quiz_answers=answers
    )
    await callback.message.edit_text(result_text, reply_markup=quiz_result_keyboard())


@router.callback_query(QuizStates.finished, QuizResultActionCallback.filter())
async def handle_quiz_result_action(
    callback: CallbackQuery, callback_data: QuizResultActionCallback, state: FSMContext
) -> None:
    """Действия после финального экрана квиза."""
    await callback.answer()
    if not callback.from_user:
        return

    user = await User.get_or_none(telegram_id=callback.from_user.id)
    if not user:
        await callback.message.edit_text("Сначала напиши /start.")
        return

    if callback_data.action == QuizAction.later:
        await state.clear()
        await callback.message.edit_text(
            "Окей, без проблем. Когда захочешь начать — жми /start",
            reply_markup=main_menu_keyboard(),
        )
        return

    await state.update_data(onboarding_sprint=True)

    # Стартуем мини-спринт через утренний поток
    from src.bot.handlers.morning import start_onboarding_sprint_flow

    try:
        await start_onboarding_sprint_flow(target=callback, state=state, user=user)
    except Exception as err:  # noqa: BLE001
        logger.exception("Failed to launch onboarding sprint: %s", err)
        await callback.message.edit_text(
            "Не вышло запустить мини-спринт. Попробуй /morning или /start."
        )
