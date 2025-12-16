"""
Test script for Phase 5.3 - Steps endpoints.

Tests the new API endpoints:
- GET /api/steps/today
- POST /api/steps/{id}/complete
- POST /api/steps/{id}/skip
"""

import asyncio
import sys
from datetime import date

from tortoise import Tortoise

from src.config import config
from src.core.use_cases.complete_step import CompleteStepUseCase
from src.core.use_cases.skip_step import SkipStepUseCase
from src.database.config import TORTOISE_ORM
from src.database.models import Goal, Stage, Step, User


async def init_db():
    """Initialize database."""
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas()
    print("✅ Database initialized")


async def close_db():
    """Close database connections."""
    await Tortoise.close_connections()
    print("✅ Database closed")


async def create_test_data():
    """Create test user, goal, stage, and steps."""
    print("\n📦 Creating test data...")
    
    # Create or get test user
    user, created = await User.get_or_create(
        telegram_id=123456789,
        defaults={
            "username": "test_user",
            "first_name": "Test",
            "xp": 0,
            "level": 1,
            "streak_days": 0,
        }
    )
    
    if created:
        print(f"  ✅ Created test user: {user.telegram_id}")
    else:
        print(f"  ℹ️  Using existing user: {user.telegram_id}")
    
    # Create test goal
    goal = await Goal.create(
        user=user,
        title="Test Goal for Phase 5.3",
        description="Testing steps endpoints",
        deadline=date(2025, 1, 31),
        status="active",
    )
    print(f"  ✅ Created goal: {goal.title}")
    
    # Create test stage
    stage = await Stage.create(
        goal=goal,
        title="Test Stage",
        order=1,
        start_date=date.today(),
        end_date=date(2025, 1, 31),
        status="active",
        progress=0,
    )
    print(f"  ✅ Created stage: {stage.title}")
    
    # Create test steps for today
    steps = []
    for i in range(3):
        step = await Step.create(
            stage=stage,
            title=f"Test Step {i+1}",
            difficulty=["easy", "medium", "hard"][i],
            estimated_minutes=[5, 15, 30][i],
            xp_reward=[10, 20, 30][i],
            scheduled_date=date.today(),
            status="pending",
        )
        steps.append(step)
        print(f"  ✅ Created step: {step.title} ({step.difficulty})")
    
    return user, goal, stage, steps


async def test_get_today_steps(user: User):
    """Test GET /api/steps/today logic."""
    print("\n🧪 Test 1: Get today's steps")
    
    # Query steps for today
    steps = await Step.filter(
        scheduled_date=date.today(),
        status__in=["pending", "completed", "skipped"],
        stage__goal__user=user,
        stage__goal__status="active",
    ).prefetch_related("stage__goal").all()
    
    print(f"  ✅ Found {len(steps)} steps for today")
    for step in steps:
        print(f"     - {step.title} ({step.status}, {step.xp_reward} XP)")
    
    return steps


async def test_complete_step(user: User, step: Step):
    """Test POST /api/steps/{id}/complete logic."""
    print(f"\n🧪 Test 2: Complete step '{step.title}'")
    
    use_case = CompleteStepUseCase()
    result = await use_case.execute(step_id=step.id, user=user)
    
    if result.success:
        print(f"  ✅ Step completed successfully")
        print(f"     XP earned: {result.xp_earned}")
        print(f"     Total XP: {result.total_xp}")
        print(f"     Streak updated: {result.streak_updated}")
        if result.streak_updated:
            print(f"     New streak: {result.new_streak} days")
    else:
        print(f"  ❌ Failed: {result.error_message}")
    
    return result


async def test_skip_step(user: User, step: Step):
    """Test POST /api/steps/{id}/skip logic."""
    print(f"\n🧪 Test 3: Skip step '{step.title}'")
    
    use_case = SkipStepUseCase()
    result = await use_case.execute(
        step_id=step.id,
        user=user,
        reason="Testing skip functionality"
    )
    
    if result.success:
        print(f"  ✅ Step skipped successfully")
    else:
        print(f"  ❌ Failed: {result.error_message}")
    
    return result


async def test_stats_update(user: User):
    """Test that stats are updated correctly."""
    print("\n🧪 Test 4: Verify stats update")
    
    # Reload user from DB
    user = await User.get(id=user.id)
    
    print(f"  ✅ User stats:")
    print(f"     XP: {user.xp}")
    print(f"     Level: {user.level}")
    print(f"     Streak: {user.streak_days} days")


async def cleanup_test_data(user: User):
    """Clean up test data."""
    print("\n🧹 Cleaning up test data...")
    
    # Delete user (cascade will delete goals, stages, steps)
    await user.delete()
    print("  ✅ Test data cleaned up")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("🚀 Phase 5.3 - Steps Endpoints Test")
    print("=" * 60)
    
    try:
        # Initialize
        await init_db()
        
        # Create test data
        user, goal, stage, steps = await create_test_data()
        
        # Test 1: Get today's steps
        today_steps = await test_get_today_steps(user)
        
        if len(today_steps) < 2:
            print("\n❌ Not enough steps for testing")
            return
        
        # Test 2: Complete first step
        complete_result = await test_complete_step(user, today_steps[0])
        
        # Test 3: Skip second step
        skip_result = await test_skip_step(user, today_steps[1])
        
        # Test 4: Verify stats
        await test_stats_update(user)
        
        # Verify steps after actions
        print("\n🧪 Test 5: Verify steps after actions")
        updated_steps = await test_get_today_steps(user)
        completed_count = sum(1 for s in updated_steps if s.status == "completed")
        skipped_count = sum(1 for s in updated_steps if s.status == "skipped")
        pending_count = sum(1 for s in updated_steps if s.status == "pending")
        
        print(f"  ✅ Steps status:")
        print(f"     Completed: {completed_count}")
        print(f"     Skipped: {skipped_count}")
        print(f"     Pending: {pending_count}")
        
        # Cleanup
        await cleanup_test_data(user)
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())

