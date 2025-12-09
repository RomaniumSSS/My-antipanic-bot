"""
Stuck handlers — помощь при застревании.

Flow:
1. Пользователь нажимает "Застрял" на шаге
2. Выбирает тип блокера
3. Если "unclear" — запрос деталей
4. AI генерирует микро-удар
"""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from src.bot.callbacks.data import BlockerCallback, BlockerType
from src.bot.states import StuckStates
from src.bot.keyboards import steps_list_keyboard
from src.database.models import User, DailyLog, Step
from src.services.ai import ai_service
from datetime import date

logger = logging.getLogger(__name__)

router = Router()


# Описания блокеров для промпта
BLOCKER_DESCRIPTIONS = {
    BlockerType.fear: "страшно, тревожно браться за задачу",
    BlockerType.unclear: "не понимает с чего начать",
    BlockerType.no_time: "кажется что нет времени",
    BlockerType.no_energy: "нет сил и энергии",
}


@router.callback_query(
    StuckStates.waiting_for_blocker,
    BlockerCallback.filter(F.type == BlockerType.unclear),
)
async def blocker_unclear(callback: CallbackQuery, state: FSMContext) -> None:
    """Блокер "не знаю с чего начать" — запрашиваем детали."""
    await callback.answer()

    await state.update_data(blocker_type=BlockerType.unclear.value)
    await state.set_state(StuckStates.waiting_for_details)

    data = await state.get_data()
    step_title = data.get("stuck_step_title", "задача")

    await callback.message.edit_text(
        f"Понял, не знаешь с чего начать *{step_title}*.\n\n"
        "Расскажи подробнее — что именно непонятно?\n"
        "Или напиши `-` если не хочешь уточнять."
    )


@router.callback_query(StuckStates.waiting_for_blocker, BlockerCallback.filter())
async def blocker_other(
    callback: CallbackQuery, callback_data: BlockerCallback, state: FSMContext
) -> None:
    """Обработка других типов блокеров — сразу к микро-удару."""
    await callback.answer()

    blocker_type = callback_data.type
    await state.update_data(blocker_type=blocker_type.value)

    # Генерируем микро-удар
    await generate_and_show_microhit(callback.message, state, details="")


@router.message(StuckStates.waiting_for_details)
async def process_details(message: Message, state: FSMContext) -> None:
    """Получение деталей и генерация микро-удара."""
    details = message.text or ""
    if details == "-":
        details = ""

    await generate_and_show_microhit(message, state, details)


async def generate_and_show_microhit(
    message_or_callback_msg, state: FSMContext, details: str
) -> None:
    """Генерация и показ микро-удара."""
    data = await state.get_data()
    step_title = data.get("stuck_step_title", "задача")
    blocker_type = data.get("blocker_type", "unclear")

    # Отправляем индикатор загрузки
    if hasattr(message_or_callback_msg, "edit_text"):
        wait_msg = await message_or_callback_msg.edit_text(
            "🤔 Думаю над микро-ударом..."
        )
    else:
        wait_msg = await message_or_callback_msg.answer("🤔 Думаю над микро-ударом...")

    # Генерируем микро-удар
    valid_types = [b.value for b in BlockerType]
    if blocker_type in valid_types:
        blocker_key = BlockerType(blocker_type)
    else:
        blocker_key = BlockerType.unclear
    blocker_desc = BLOCKER_DESCRIPTIONS.get(blocker_key, blocker_type)

    microhit = await ai_service.get_microhit(
        step_title=step_title, blocker_type=blocker_desc, details=details
    )

    await state.clear()

    # Показываем микро-удар
    blocker_emoji = {
        "fear": "😨",
        "unclear": "🤷",
        "no_time": "⏰",
        "no_energy": "😴",
    }.get(blocker_type, "🔧")

    # Получаем список оставшихся шагов для кнопок
    reply_markup = None
    if hasattr(message_or_callback_msg, "from_user"):
        from_user = message_or_callback_msg.from_user
        user_id = from_user.id if from_user else None
    elif hasattr(message_or_callback_msg, "chat"):
        user_id = message_or_callback_msg.chat.id
    else:
        user_id = None

    if user_id:
        user = await User.get_or_none(telegram_id=user_id)
        if user:
            today = date.today()
            daily_log = await DailyLog.get_or_none(user=user, date=today)
            if daily_log and daily_log.assigned_step_ids:
                steps = await Step.filter(
                    id__in=daily_log.assigned_step_ids, status="pending"
                )
                if steps:
                    reply_markup = steps_list_keyboard([s.id for s in steps])

    result_text = (
        f"{blocker_emoji} *Микро-удар:*\n\n"
        f"{microhit}\n\n"
        f"💡 Попробуй это прямо сейчас — всего 2-5 минут!"
    )

    if hasattr(wait_msg, "edit_text"):
        await wait_msg.edit_text(result_text, reply_markup=reply_markup)
    else:
        await message_or_callback_msg.answer(result_text, reply_markup=reply_markup)

    logger.info(f"Microhit generated for step '{step_title}' blocker='{blocker_type}'")
