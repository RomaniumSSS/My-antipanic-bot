# mypy (Quick Reference)

## Run checks

```bash
mypy src/                    # Check all
mypy src/bot/handlers/       # Check specific dir
mypy --strict src/           # Strict mode
```

## Common patterns

```python
# Tortoise ORM
user: User | None = await User.get_or_none(telegram_id=123)
if not user:
    return

# ForeignKey relations
class Goal(Model):
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(...)

# Reverse relations
class User(Model):
    goals: fields.ReverseRelation["Goal"]

# FSM
data = await state.get_data()
goal_id: int | None = data.get("goal_id")
```

## Config

`mypy.ini`:
```ini
[mypy]
python_version = 3.11
ignore_missing_imports = True
```
