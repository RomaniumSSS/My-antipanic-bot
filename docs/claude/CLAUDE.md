# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Antipanic Bot is an async Telegram bot built on aiogram 3.x that helps users overcome procrastination paralysis through goal decomposition, daily micro-steps, and anti-stuck mechanisms. The bot uses Claude Sonnet 4.5 (Anthropic) for intelligent task generation with drill sergeant tone and APScheduler for reminders.

## Quick Start Commands

### Running the Bot
```bash
python -m src.main
```

### Database Migrations
```bash
# Initialize aerich (first time only)
aerich init -t src.database.config.TORTOISE_ORM

# Generate migration
aerich migrate

# Apply migrations
aerich upgrade
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_morning.py

# Run with verbose output
pytest -v

# Run specific test
pytest tests/test_quiz.py::test_quiz_scoring
```

### Code Quality
```bash
# Format code
ruff format .

# Lint
ruff check .

# Fix auto-fixable issues
ruff check --fix .
```

## Environment Setup

Required `.env` variables:
- `BOT_TOKEN` - Telegram Bot API token
- `ANTHROPIC_KEY` - Anthropic API key for Claude
- `AI_PROVIDER` - "anthropic" (default) or "openai" (fallback)
- `OPENAI_KEY` - OpenAI API key (optional, for fallback)
- `ALLOWED_USER_IDS` - Optional whitelist (comma-separated IDs or JSON array)

## Critical Architecture Patterns

### 1. FSM Flow Structure

The bot implements multiple FSM flows that are carefully orchestrated:

**Flow Hierarchy:**
1. **Quiz → Onboarding → Morning (Antipanic)** - Initial user journey
2. **Morning (Antipanic) → Stuck → Evening** - Daily cycle

**Key State Groups** (`src/bot/states.py`):
- `QuizStates` - Pre-onboarding assessment
- `OnboardingStates` - First goal creation
- `AntipanicSession` - Fast-action morning flow (new design)
- `MorningStates` - Traditional morning ritual (legacy)
- `StuckStates` - Blocker resolution
- `EveningStates` - Daily reflection

**State Transition Logic:**
- Quiz completes → triggers OnboardingStates
- Onboarding creates Goal with Stages → enables morning flows
- AntipanicSession provides rapid tension-reduction path
- All flows log to DailyLog for consistency

### 2. Data Model Relationships

**Core Models** (`src/database/models.py`):
```
User (1) ──→ (N) Goal ──→ (N) Stage ──→ (N) Step
  │                                         │
  └──→ (N) DailyLog ←─────────────────────┘
  └──→ (N) QuizResult
```

**Critical Relationships:**
- `Goal.status` values: `"active"`, `"onboarding"`, `"completed"`, `"paused"`, `"abandoned"`
- `Stage.status` values: `"pending"`, `"active"`, `"completed"`
- **Onboarding goals** (`status="onboarding"`) have special rules in `session.py:ensure_active_stage()` - they don't auto-complete stages at 100% progress to allow continuous micro-step addition

**DailyLog Integration:**
- ALL step creation must call `session.log_antipanic_action()` to maintain stats consistency
- `assigned_step_ids` tracks what was offered
- `completed_step_ids` tracks what was done
- `xp_earned` accumulates from completed steps
- `energy_level` and `mood_text` capture daily state

### 3. Session Logic Pattern (`src/services/session.py`)

**Key Function: `ensure_active_stage(goal)`**
- Handles multiple active stages (keeps latest, marks others pending)
- Auto-completes stages at 100% progress (except onboarding goals)
- Auto-activates next pending stage
- Creates default stage if none exist
- Marks goal completed when all stages done

**Step Creation Pattern:**
```python
# Always use this pattern:
step = await Step.create(...)
await log_antipanic_action(
    user=user,
    step=step,
    energy_hint=energy,
    mood_hint=mood,
    completed=False  # or True if immediately done
)
```

### 4. AI Service Integration (`src/services/ai.py`)

**Critical Patterns:**
- Always use `AsyncAnthropic` client (never sync!) - migrated from OpenAI (plan 003)
- Claude API requires `max_tokens` parameter (MANDATORY, unlike OpenAI)
- System prompt passed as separate parameter, not in messages
- All prompts use drill sergeant tone (no "попробуй", "может быть")
- Retry logic via tenacity for transient errors
- Short timeouts (60s) with fallback messages
- Energy-aware step generation (low energy = easy steps only)
- Fallback to OpenAI via `AI_PROVIDER=openai` in .env

**Key Methods:**
- `generate_steps()` - Daily task list based on energy/mood
- `generate_micro_step()` - Single 2-5 min action
- `get_microhit()` - Legacy: single anti-stuck action
- `get_microhit_variants()` - NEW: 2-3 variant options for user choice (plan 003)
- `generate_quiz_diagnosis()` - Quiz analysis with drill sergeant tone

### 5. CallbackData Architecture

**CRITICAL: Never use raw callback_data strings!**

All callbacks use typed factories in `src/bot/callbacks/data.py`:
```python
# Good:
EnergyCallback(action=EnergyAction.set, value=7)

# Bad:
callback_data="energy:7"  # NEVER DO THIS
```

**Callback Filtering Pattern:**
```python
@router.callback_query(EnergyCallback.filter(F.action == EnergyAction.set))
async def handler(callback: CallbackQuery, callback_data: EnergyCallback):
    value = callback_data.value  # Type-safe
```

## Common Development Patterns

### Adding a New Bot Flow

1. Define states in `src/bot/states.py`:
```python
class MyFlowStates(StatesGroup):
    step_one = State()
    step_two = State()
```

2. Create handler in `src/bot/handlers/myflow.py`:
```python
router = Router(name="myflow")

@router.message(Command("myflow"))
async def start_flow(message: Message, state: FSMContext):
    await state.set_state(MyFlowStates.step_one)
    ...
```

3. Register in `src/bot/handlers/__init__.py`:
```python
from . import myflow

def register_routers(dp: Dispatcher):
    dp.include_router(myflow.router)
```

### Working with Steps and Progress

When creating steps programmatically:
```python
from src.services.session import ensure_active_stage, log_antipanic_action

# 1. Get/create active stage
stage = await ensure_active_stage(goal)
if not stage:
    raise ValueError("No active stage")

# 2. Create step
step = await Step.create(
    stage=stage,
    title="My task",
    difficulty="easy",  # easy/medium/hard
    estimated_minutes=5,
    xp_reward=10,
    scheduled_date=date.today(),
    status="pending"
)

# 3. ALWAYS log to DailyLog
await log_antipanic_action(
    user=user,
    step=step,
    energy_hint=5,
    mood_hint="focused"
)
```

### Updating Stage Progress

Progress is calculated from completed steps:
```python
# After completing a step:
step.status = "completed"
await step.save()

# Recalculate stage progress
total_steps = await Step.filter(stage=stage).count()
completed_steps = await Step.filter(stage=stage, status="completed").count()

stage.progress = int((completed_steps / total_steps) * 100) if total_steps > 0 else 0
await stage.save()

# Check if stage should auto-complete
await ensure_active_stage(goal)  # Handles completion logic
```

## Critical Rules to Follow

### aiogram 3.x Rules (docs/guides/AIOGRAM_RULES.md)
1. **Always** use CallbackData factories, never raw strings
2. **Always** call `callback.answer()` or use CallbackAnswerMiddleware
3. Use Magic Filter `F` for all filtering (`F.text`, `F.from_user.id`, etc.)
4. FSM data via `state.update_data()` and `state.get_data()`
5. One router per major flow
6. No business logic in handlers - delegate to services

### Tortoise ORM Rules (docs/guides/TORTOISE_RULES.md)
1. **Always** use `prefetch_related()` or `select_related()` to avoid N+1 queries
2. **Always** await database operations
3. Use `ForeignKeyRelation` type hints for type safety
4. Wrap related operations in `async with in_transaction():`
5. Use `get_or_create()` for idempotent inserts

### Claude API Rules (docs/guides/CLAUDE_RULES.md)
1. **Only** use `AsyncAnthropic` client (NEVER sync!)
2. **max_tokens** MANDATORY parameter (unlike OpenAI)
3. API keys from config, never hardcoded
4. Implement retry with tenacity for transient errors
5. Always have fallback messages
6. Structure prompts in constants
7. Drill sergeant tone (no "попробуй", "может быть")
8. Energy-based generation: low energy (1-3) = only easy steps

### APScheduler Rules (docs/APSCHEDULER_RULES.md)
1. Use `AsyncScheduler` for async jobs
2. Specify `conflict_policy` when using fixed job IDs
3. Start scheduler in `on_startup`, stop in `on_shutdown`
4. Pass bot instance to jobs via scheduler context

## Testing Patterns

### Test Structure
```python
@pytest.mark.asyncio
async def test_my_feature(mock_bot, mock_user):
    # Arrange
    user = await User.create(telegram_id=12345, ...)

    # Act
    result = await my_function(user)

    # Assert
    assert result == expected

    # Verify database state
    saved = await User.get(telegram_id=12345)
    assert saved.xp == 10
```

### Mock Bot and User
Fixtures available in `tests/conftest.py`:
- `mock_bot` - Mock Bot instance
- `mock_user` - Mock Telegram User
- `test_user` - Real User model instance

## Documentation Requirements

**When making significant changes, update:**
- `docs/tech/tech.md` - Architecture, data models, integrations
- `docs/product/product.md` - User flows, business logic
- `docs/guides/AIOGRAM_RULES.md` - Bot patterns
- `docs/guides/TORTOISE_RULES.md` - Database patterns
- `docs/guides/CLAUDE_RULES.md` - AI integration patterns (Claude API)
- `docs/guides/AGENTS.md` - AI agent instructions

**Do NOT update documentation for:**
- Simple refactors without logic changes
- Minor bug fixes
- Dependency updates
- Code formatting

## Key Files Reference

- `src/main.py` - Entry point, dispatcher setup
- `src/config.py` - Settings from environment
- `src/database/models.py` - Data models
- `src/database/config.py` - Tortoise ORM config
- `src/bot/states.py` - FSM state definitions
- `src/bot/callbacks/data.py` - CallbackData factories
- `src/bot/keyboards.py` - Keyboard builders
- `src/bot/middlewares/access.py` - Whitelist middleware
- `src/services/ai.py` - Claude/OpenAI wrapper (AI service)
- `src/services/scheduler.py` - APScheduler wrapper
- `src/services/session.py` - Session management, step creation, DailyLog integration

## Debugging Tips

### Check Active Stages
```bash
python -m src.scripts.check_stages
```

### Recalculate Progress
```bash
python -m src.scripts.recalc_progress
```

### Enable Debug Logging
```python
logging.basicConfig(level=logging.DEBUG)
```

### Common Issues

**Multiple active stages:** `ensure_active_stage()` fixes automatically by keeping latest

**Steps not showing in stats:** Verify `log_antipanic_action()` was called

**Stage not completing:** Check if goal.status is "onboarding" (special rules apply)

**Callbacks not working:** Ensure CallbackData factory is registered and filtered correctly

## Anti-Patterns to Avoid

1. ❌ Raw callback_data strings
2. ❌ Creating steps without calling `log_antipanic_action()`
3. ❌ Forgetting `await` on database operations
4. ❌ N+1 queries (missing prefetch_related)
5. ❌ Business logic in handlers instead of services
6. ❌ Hardcoded API keys
7. ❌ Sync Claude or OpenAI client (NEVER sync in async context!)
8. ❌ Forgetting to update stage progress after completing steps
9. ❌ Manually managing active stage state (use `ensure_active_stage()`)
10. ❌ Creating goals/stages without proper status initialization
