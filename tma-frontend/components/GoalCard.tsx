'use client';

import type { GoalListItem } from '@/lib/api';

interface GoalCardProps {
  goal: GoalListItem;
  onClick?: () => void;
}

export function GoalCard({ goal, onClick }: GoalCardProps) {
  const statusConfig = getStatusConfig(goal.status);
  const daysLeft = getDaysLeft(goal.deadline);

  return (
    <div
      className="card cursor-pointer active:scale-[0.98] transition-transform"
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-base truncate">{goal.title}</h3>
          <div className="flex items-center gap-2 mt-1">
            <span className={`text-xs px-2 py-0.5 rounded-full ${statusConfig.className}`}>
              {statusConfig.label}
            </span>
            {daysLeft !== null && (
              <span className="text-xs hint-text">
                {daysLeft > 0 ? `${daysLeft} дн. осталось` : daysLeft === 0 ? 'Сегодня!' : 'Просрочено'}
              </span>
            )}
          </div>
        </div>
        <div className="text-2xl">{statusConfig.emoji}</div>
      </div>
    </div>
  );
}

function getStatusConfig(status: string): { label: string; emoji: string; className: string } {
  switch (status) {
    case 'active':
      return { label: 'В работе', emoji: '🎯', className: 'bg-blue-100 text-blue-700' };
    case 'completed':
      return { label: 'Выполнено', emoji: '✅', className: 'bg-green-100 text-green-700' };
    case 'paused':
      return { label: 'На паузе', emoji: '⏸️', className: 'bg-yellow-100 text-yellow-700' };
    case 'abandoned':
      return { label: 'Отменено', emoji: '❌', className: 'bg-gray-100 text-gray-600' };
    default:
      return { label: status, emoji: '📋', className: 'bg-gray-100 text-gray-600' };
  }
}

function getDaysLeft(deadline: string): number | null {
  try {
    const deadlineDate = new Date(deadline);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    deadlineDate.setHours(0, 0, 0, 0);
    const diffTime = deadlineDate.getTime() - today.getTime();
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  } catch {
    return null;
  }
}

export function GoalCardSkeleton() {
  return (
    <div className="card">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 space-y-2">
          <div className="skeleton h-5 w-3/4 rounded" />
          <div className="flex gap-2">
            <div className="skeleton h-5 w-16 rounded-full" />
            <div className="skeleton h-5 w-24 rounded" />
          </div>
        </div>
        <div className="skeleton h-8 w-8 rounded" />
      </div>
    </div>
  );
}

interface GoalsListProps {
  goals: GoalListItem[];
  onGoalClick?: (goalId: number) => void;
}

export function GoalsList({ goals, onGoalClick }: GoalsListProps) {
  if (goals.length === 0) {
    return (
      <div className="card text-center py-8">
        <div className="text-4xl mb-3">🎯</div>
        <div className="font-medium">Пока нет целей</div>
        <div className="text-sm hint-text mt-1">
          Создай цель в боте, чтобы начать
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {goals.map((goal) => (
        <GoalCard
          key={goal.id}
          goal={goal}
          onClick={() => onGoalClick?.(goal.id)}
        />
      ))}
    </div>
  );
}
