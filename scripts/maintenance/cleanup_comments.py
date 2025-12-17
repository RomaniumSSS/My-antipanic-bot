"""
Скрипт для очистки устаревших AICODE-NOTE комментариев.

Удаляет комментарии о:
- TMA миграции (уже завершена)
- Удалённых features (Quiz, Plan 005)
- Завершённых рефакторингах
"""

import re
from pathlib import Path

# Паттерны устаревших комментариев для удаления
PATTERNS_TO_REMOVE = [
    # TMA миграция
    r'AICODE-NOTE:.*TMA migration.*\n',
    r'AICODE-NOTE:.*Этап \d+\.\d+.*миграц.*\n',
    r'AICODE-NOTE:.*Упрощено для.*TMA.*\n',
    r'.*Refactored in Stage.*TMA.*\n',

    # Quiz/QuizResult
    r'AICODE-NOTE:.*quiz.*\n',
    r'AICODE-NOTE:.*QuizResult.*\n',

    # Plan 005
    r'AICODE-NOTE:.*Plan 005.*\n',
    r'AICODE-NOTE:.*daily_time_budget.*\n',

    # Миграция Claude
    r'AICODE-NOTE:.*миграц.*OpenAI.*Claude.*\n',

    # Удалённые состояния
    r'.*Удалены неиспользуемые states.*\n',
    r'.*Убрано состояние.*\n',
    r'.*Удалено состояние.*\n',
]

# Многострочные комментарии для упрощения
MULTILINE_SIMPLIFICATIONS = [
    # Убрать детали TMA миграции из docstrings
    (
        r'"""([^\n]*)\n\nAICODE-NOTE:.*миграц.*\n.*\n"""',
        r'"""\1"""'
    ),
]


def cleanup_file(file_path: Path) -> tuple[int, str]:
    """
    Очистить один файл от устаревших комментариев.

    Returns:
        (changes_count, new_content)
    """
    content = file_path.read_text(encoding='utf-8')
    original = content
    changes = 0

    # Удалить однострочные паттерны
    for pattern in PATTERNS_TO_REMOVE:
        new_content = re.sub(pattern, '', content, flags=re.IGNORECASE)
        if new_content != content:
            changes += 1
            content = new_content

    # Упростить многострочные
    for pattern, replacement in MULTILINE_SIMPLIFICATIONS:
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL | re.IGNORECASE)
        if new_content != content:
            changes += 1
            content = new_content

    return changes, content if changes > 0 else original


def main():
    """Запустить очистку для всех Python файлов в src/."""
    src_dir = Path(__file__).parent.parent / 'src'

    total_files = 0
    total_changes = 0
    modified_files = []

    for py_file in src_dir.rglob('*.py'):
        if '__pycache__' in str(py_file):
            continue

        total_files += 1
        changes, new_content = cleanup_file(py_file)

        if changes > 0:
            # Сохранить изменения
            py_file.write_text(new_content, encoding='utf-8')
            total_changes += changes
            modified_files.append((py_file.relative_to(src_dir), changes))
            print(f"✅ {py_file.relative_to(src_dir)}: {changes} изменений")

    print("\n📊 Итого:")
    print(f"   Проверено файлов: {total_files}")
    print(f"   Изменено файлов: {len(modified_files)}")
    print(f"   Всего изменений: {total_changes}")

    if modified_files:
        print("\n📝 Изменённые файлы:")
        for file, count in modified_files:
            print(f"   - {file}: {count} изменений")


if __name__ == '__main__':
    main()
