'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTelegram } from '@/app/providers';
import { getMe, getStats, type User, type Stats } from '@/lib/api';
import { hapticFeedback } from '@/lib/telegram';

type LoadingState = 'loading' | 'ready' | 'error';

export default function StatsPage() {
  const router = useRouter();
  const { isReady, isInTelegram } = useTelegram();

  const [loadingState, setLoadingState] = useState<LoadingState>('loading');
  const [user, setUser] = useState<User | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isReady) return;

    async function loadData() {
      try {
        const [userData, statsData] = await Promise.all([getMe(), getStats()]);
        setUser(userData);
        setStats(statsData);
        setLoadingState('ready');
        hapticFeedback('success');
      } catch (err) {
        console.error('Failed to load stats:', err);
        setError(err instanceof Error ? err.message : 'Не удалось загрузить статистику');
        setLoadingState('error');
        hapticFeedback('error');
      }
    }

    if (isInTelegram) {
      loadData();
    } else {
      setLoadingState('ready');
    }
  }, [isReady, isInTelegram]);

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
        <h1 className="text-xl font-bold mb-2">Что-то пошло не так</h1>
        <p className="hint-text mb-4">{error}</p>
        <button className="btn-primary" onClick={() => router.push('/')}>
          Вернуться на главную
        </button>
      </div>
    );
  }

  // Loading state
  if (loadingState === 'loading' || !stats || !user) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <div className="text-4xl mb-4 animate-pulse">📊</div>
        <p className="hint-text">Загрузка статистики...</p>
      </div>
    );
  }

  const levelProgress = (stats.xp / (stats.xp + stats.xp_to_next_level)) * 100;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <button
          className="text-2xl hover:opacity-70"
          onClick={() => {
            hapticFeedback('light');
            router.back();
          }}
        >
          ←
        </button>
        <h1 className="text-2xl font-bold">📊 Статистика</h1>
      </div>

      {/* XP & Level */}
      <section className="card">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-2xl font-bold">Уровень {stats.level}</h2>
            <p className="text-sm hint-text">
              {stats.xp} / {stats.xp + stats.xp_to_next_level} XP
            </p>
          </div>
          <div className="text-5xl">⭐</div>
        </div>

        {/* Level progress bar */}
        <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all duration-500"
            style={{ width: `${levelProgress}%` }}
          />
        </div>

        <p className="text-xs hint-text mt-2">
          До следующего уровня: {stats.xp_to_next_level} XP
        </p>
      </section>

      {/* Streak */}
      <section className="card">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold mb-1">🔥 Streak</h3>
            <p className="hint-text text-sm">Дней подряд</p>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-orange-600">{stats.streak_days}</div>
            <p className="text-xs hint-text">
              {stats.streak_days === 0
                ? 'Начни сегодня!'
                : stats.streak_days === 1
                ? 'Продолжай!'
                : stats.streak_days < 7
                ? 'Почти неделя!'
                : stats.streak_days < 30
                ? 'Отличная форма!'
                : 'Легенда!'}
            </p>
          </div>
        </div>
      </section>

      {/* Goals Overview */}
      <section className="card">
        <h3 className="text-lg font-semibold mb-4">🎯 Цели</h3>

        <div className="space-y-3">
          {/* Total goals */}
          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span className="text-sm text-gray-600">Всего целей</span>
            <span className="font-bold text-lg">{stats.total_goals}</span>
          </div>

          {/* Active goals */}
          <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
            <span className="text-sm text-blue-700">Активных</span>
            <span className="font-bold text-lg text-blue-600">{stats.active_goals}</span>
          </div>

          {/* Completed goals */}
          <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
            <span className="text-sm text-green-700">Завершено</span>
            <span className="font-bold text-lg text-green-600">{stats.completed_goals}</span>
          </div>
        </div>
      </section>

      {/* Steps Statistics */}
      <section className="card">
        <h3 className="text-lg font-semibold mb-4">👣 Шаги</h3>

        <div className="grid grid-cols-2 gap-3">
          {/* Total steps */}
          <div className="p-4 bg-gray-50 rounded-lg text-center">
            <div className="text-2xl font-bold text-gray-800">
              {stats.total_steps_completed}
            </div>
            <div className="text-xs hint-text mt-1">Всего выполнено</div>
          </div>

          {/* Steps today */}
          <div className="p-4 bg-green-50 rounded-lg text-center">
            <div className="text-2xl font-bold text-green-600">{stats.steps_today}</div>
            <div className="text-xs text-green-700 mt-1">Сегодня</div>
          </div>
        </div>

        {/* Completion rate */}
        <div className="mt-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-600">Completion Rate</span>
            <span className="font-semibold">{Math.round(stats.completion_rate * 100)}%</span>
          </div>

          <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ${
                stats.completion_rate >= 0.8
                  ? 'bg-green-500'
                  : stats.completion_rate >= 0.5
                  ? 'bg-yellow-500'
                  : 'bg-red-500'
              }`}
              style={{ width: `${stats.completion_rate * 100}%` }}
            />
          </div>

          <p className="text-xs hint-text mt-2">
            {stats.completion_rate >= 0.8
              ? '🎉 Отличный показатель!'
              : stats.completion_rate >= 0.5
              ? '💪 Хороший темп, продолжай!'
              : '🚀 Есть куда расти!'}
          </p>
        </div>
      </section>

      {/* Motivational Message */}
      <section className="card bg-gradient-to-r from-blue-50 to-purple-50 border border-blue-200">
        <div className="text-center">
          <div className="text-4xl mb-3">
            {stats.streak_days >= 30
              ? '👑'
              : stats.streak_days >= 7
              ? '🔥'
              : stats.total_steps_completed >= 50
              ? '⭐'
              : stats.total_steps_completed >= 10
              ? '💪'
              : '🚀'}
          </div>
          <p className="font-medium text-gray-800 mb-1">
            {stats.streak_days >= 30
              ? 'Легендарный streak! Ты монстр продуктивности!'
              : stats.streak_days >= 7
              ? 'Неделя без пропусков! Машина!'
              : stats.total_steps_completed >= 50
              ? 'Уже 50+ шагов! Продолжай в том же духе!'
              : stats.total_steps_completed >= 10
              ? 'Отличное начало! Первые 10 шагов пройдены!'
              : 'Каждый шаг приближает тебя к цели!'}
          </p>
          <p className="text-sm hint-text">
            Следующий микрошаг — и ты станешь ещё сильнее 💪
          </p>
        </div>
      </section>

      {/* Back button */}
      <button
        className="btn-primary w-full"
        onClick={() => {
          hapticFeedback('light');
          router.push('/');
        }}
      >
        ← На главную
      </button>
    </div>
  );
}

