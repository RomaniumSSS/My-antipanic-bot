'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useTelegram } from '@/app/providers';
import {
  StageCard,
  StageCardSkeleton,
} from '@/components';
import { getGoal, type GoalDetail } from '@/lib/api';
import { hapticFeedback } from '@/lib/telegram';

type LoadingState = 'loading' | 'ready' | 'error';

export default function GoalDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { isReady, isInTelegram } = useTelegram();
  
  const goalId = Number(params.id);
  const [loadingState, setLoadingState] = useState<LoadingState>('loading');
  const [goal, setGoal] = useState<GoalDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isReady || !isInTelegram) return;
    if (isNaN(goalId)) {
      setError('Некорректный ID цели');
      setLoadingState('error');
      return;
    }

    async function loadGoal() {
      try {
        const data = await getGoal(goalId);
        setGoal(data);
        setLoadingState('ready');
        hapticFeedback('success');
      } catch (err) {
        console.error('Failed to load goal:', err);
        setError(err instanceof Error ? err.message : 'Не удалось загрузить цель');
        setLoadingState('error');
        hapticFeedback('error');
      }
    }

    loadGoal();
  }, [isReady, isInTelegram, goalId]);

  // Demo mode
  if (isReady && !isInTelegram) {
    return (
      <div className="space-y-6">
        <div className="card bg-blue-50 border border-blue-200">
          <div className="flex items-center gap-3">
            <span className="text-2xl">📱</span>
            <div>
              <div className="font-medium text-blue-900">Демо-режим</div>
              <div className="text-sm text-blue-700">
                Откройте через Telegram для полного функционала
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (loadingState === 'error') {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
        <div className="text-6xl mb-4">😔</div>
        <h1 className="text-xl font-bold mb-2">Цель не найдена</h1>
        <p className="hint-text mb-4">{error}</p>
        <button
          className="btn-primary"
          onClick={() => router.push('/')}
        >
          Вернуться на главную
        </button>
      </div>
    );
  }

  // Loading state
  if (loadingState === 'loading' || !goal) {
    return (
      <div className="space-y-6">
        {/* Header skeleton */}
        <div className="flex items-center gap-3 mb-4">
          <button className="text-2xl" onClick={() => router.back()}>
            ←
          </button>
          <div className="skeleton h-8 w-3/4 rounded" />
        </div>

        {/* Goal info skeleton */}
        <div className="card space-y-2">
          <div className="skeleton h-4 w-1/2 rounded" />
          <div className="skeleton h-4 w-2/3 rounded" />
        </div>

        {/* Stages skeleton */}
        <section>
          <div className="skeleton h-6 w-32 rounded mb-3" />
          <div className="space-y-3">
            <StageCardSkeleton />
            <StageCardSkeleton />
            <StageCardSkeleton />
          </div>
        </section>
      </div>
    );
  }

  // Find active stage
  const activeStage = goal.stages.find(s => s.status === 'active');
  const statusConfig = getGoalStatusConfig(goal.status);
  const daysLeft = getDaysLeft(goal.deadline);

  return (
    <div className="space-y-6">
      {/* Header with back button */}
      <div className="flex items-center gap-3 mb-4">
        <button
          className="text-2xl active:scale-90 transition-transform"
          onClick={() => {
            hapticFeedback('light');
            router.back();
          }}
        >
          ←
        </button>
        <h1 className="text-xl font-bold flex-1 truncate">{goal.title}</h1>
      </div>

      {/* Goal info card */}
      <div className="card space-y-3">
        {goal.description && (
          <p className="text-sm">{goal.description}</p>
        )}
        
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={`text-xs px-2 py-0.5 rounded-full ${statusConfig.className}`}>
              {statusConfig.label}
            </span>
            {daysLeft !== null && (
              <span className="text-xs hint-text">
                {daysLeft > 0
                  ? `${daysLeft} дн. до дедлайна`
                  : daysLeft === 0
                  ? 'Дедлайн сегодня!'
                  : `Просрочено на ${Math.abs(daysLeft)} дн.`}
              </span>
            )}
          </div>
          <div className="text-2xl">{statusConfig.emoji}</div>
        </div>

        <div className="text-xs hint-text pt-2 border-t border-gray-200">
          Старт: {formatDate(goal.start_date)} • Дедлайн: {formatDate(goal.deadline)}
        </div>
      </div>

      {/* Stages section */}
      <section>
        <h2 className="text-lg font-semibold mb-3">
          📋 Этапы ({goal.stages.length})
        </h2>
        
        {goal.stages.length === 0 ? (
          <div className="card text-center py-8">
            <div className="text-4xl mb-3">📋</div>
            <div className="font-medium">Нет этапов</div>
            <div className="text-sm hint-text mt-1">
              Этапы создаются автоматически при планировании
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {goal.stages.map((stage) => (
              <StageCard
                key={stage.id}
                stage={stage}
                isActive={stage.id === activeStage?.id}
              />
            ))}
          </div>
        )}
      </section>

      {/* AICODE-NOTE: Steps section will be added in phase 5.3 with /api/steps/today endpoint */}
      {activeStage && (
        <section>
          <h2 className="text-lg font-semibold mb-3">
            ⚡ Шаги текущего этапа
          </h2>
          <div className="card text-center py-6">
            <div className="text-3xl mb-2">🚧</div>
            <div className="text-sm hint-text">
              Раздел в разработке (Фаза 5.3)
            </div>
          </div>
        </section>
      )}

      {/* Footer */}
      <footer className="text-center py-4">
        <p className="text-xs hint-text">
          Antipanic Bot • Маленькие шаги, большие результаты
        </p>
      </footer>
    </div>
  );
}

function getGoalStatusConfig(status: string): {
  label: string;
  emoji: string;
  className: string;
} {
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

function formatDate(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

