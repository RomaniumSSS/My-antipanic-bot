'use client';

import type { Stats } from '@/lib/api';

interface StatsCardProps {
  stats: Stats;
}

export function StatsCard({ stats }: StatsCardProps) {
  const progressPercent = Math.min(
    100,
    Math.round((stats.xp / (stats.xp + stats.xp_to_next_level)) * 100)
  );

  return (
    <div className="card space-y-4">
      {/* Level and XP */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-2xl font-bold">Уровень {stats.level}</div>
          <div className="hint-text text-sm">
            {stats.xp} / {stats.xp + stats.xp_to_next_level} XP
          </div>
        </div>
        <div className="text-4xl">
          {stats.streak_days > 0 ? '🔥' : '💪'}
        </div>
      </div>

      {/* XP Progress bar */}
      <div className="h-2 rounded-full bg-tg-bg overflow-hidden">
        <div
          className="h-full rounded-full bg-tg-button transition-all duration-500"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-3 gap-3 pt-2">
        <StatItem
          icon="🔥"
          value={stats.streak_days}
          label="дней подряд"
        />
        <StatItem
          icon="✅"
          value={stats.steps_today}
          label="шагов сегодня"
        />
        <StatItem
          icon="🎯"
          value={stats.active_goals}
          label="активных целей"
        />
      </div>
    </div>
  );
}

interface StatItemProps {
  icon: string;
  value: number;
  label: string;
}

function StatItem({ icon, value, label }: StatItemProps) {
  return (
    <div className="text-center">
      <div className="text-xl">{icon}</div>
      <div className="text-lg font-semibold">{value}</div>
      <div className="text-xs hint-text">{label}</div>
    </div>
  );
}

export function StatsCardSkeleton() {
  return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <div className="skeleton h-7 w-32 rounded" />
          <div className="skeleton h-4 w-24 rounded" />
        </div>
        <div className="skeleton h-10 w-10 rounded-full" />
      </div>
      <div className="skeleton h-2 rounded-full" />
      <div className="grid grid-cols-3 gap-3 pt-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex flex-col items-center gap-1">
            <div className="skeleton h-6 w-6 rounded" />
            <div className="skeleton h-5 w-8 rounded" />
            <div className="skeleton h-3 w-16 rounded" />
          </div>
        ))}
      </div>
    </div>
  );
}
