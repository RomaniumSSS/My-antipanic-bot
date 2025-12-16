'use client';

import { useEffect, useState } from 'react';
import { useTelegram } from './providers';
import {
  StatsCard,
  StatsCardSkeleton,
  GoalsList,
  GoalCardSkeleton,
  UserProfile,
  UserProfileSkeleton,
  TodaySteps,
} from '@/components';
import { getMe, getStats, getGoals, type User, type Stats, type GoalsListResponse } from '@/lib/api';
import { hapticFeedback } from '@/lib/telegram';

type LoadingState = 'loading' | 'ready' | 'error';

export default function HomePage() {
  const { isReady, isInTelegram } = useTelegram();
  
  const [loadingState, setLoadingState] = useState<LoadingState>('loading');
  const [user, setUser] = useState<User | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [goals, setGoals] = useState<GoalsListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Function to reload stats after completing/skipping steps
  const reloadStats = async () => {
    try {
      const statsData = await getStats();
      setStats(statsData);
    } catch (err) {
      console.error('Failed to reload stats:', err);
    }
  };

  useEffect(() => {
    if (!isReady) return;

    async function loadData() {
      try {
        // Load all data in parallel
        const [userData, statsData, goalsData] = await Promise.all([
          getMe(),
          getStats(),
          getGoals(),
        ]);

        setUser(userData);
        setStats(statsData);
        setGoals(goalsData);
        setLoadingState('ready');
        
        // Success haptic
        hapticFeedback('success');
      } catch (err) {
        console.error('Failed to load data:', err);
        setError(err instanceof Error ? err.message : 'Не удалось загрузить данные');
        setLoadingState('error');
        
        // Error haptic
        hapticFeedback('error');
      }
    }

    // Only load data if in Telegram (has auth)
    if (isInTelegram) {
      loadData();
    } else {
      // Not in Telegram — show demo/placeholder state
      setLoadingState('ready');
    }
  }, [isReady, isInTelegram]);

  // Show demo mode notice if not in Telegram
  if (isReady && !isInTelegram) {
    return (
      <div className="space-y-6">
        {/* Demo mode banner */}
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

        {/* Demo stats */}
        <section>
          <h2 className="text-lg font-semibold mb-3">📊 Статистика</h2>
          <StatsCard stats={{
            xp: 150,
            level: 2,
            xp_to_next_level: 100,
            streak_days: 3,
            total_goals: 2,
            active_goals: 1,
            completed_goals: 1,
            total_steps_completed: 12,
            steps_today: 2,
            completion_rate: 0.75,
          }} />
        </section>

        {/* Demo goals */}
        <section>
          <h2 className="text-lg font-semibold mb-3">🎯 Цели</h2>
          <GoalsList
            goals={[
              { id: 1, title: 'Выучить TypeScript', deadline: '2025-01-15', status: 'active', created_at: '2024-12-01' },
              { id: 2, title: 'Запустить MVP', deadline: '2024-12-20', status: 'completed', created_at: '2024-11-15' },
            ]}
            onGoalClick={(id) => console.log('Demo goal clicked:', id)}
          />
        </section>

        <footer className="text-center py-4">
          <p className="text-xs hint-text">
            Antipanic Bot • Превращай большие цели в маленькие шаги
          </p>
        </footer>
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
        <button
          className="btn-primary"
          onClick={() => window.location.reload()}
        >
          Попробовать снова
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with user profile */}
      <section>
        {loadingState === 'loading' || !user ? (
          <UserProfileSkeleton />
        ) : (
          <UserProfile user={user} />
        )}
      </section>

      {/* Stats card */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">📊 Статистика</h2>
          <button
            className="text-sm text-blue-600 hover:text-blue-700 font-medium"
            onClick={() => {
              hapticFeedback('light');
              window.location.href = '/stats';
            }}
          >
            Подробнее →
          </button>
        </div>
        {loadingState === 'loading' || !stats ? (
          <StatsCardSkeleton />
        ) : (
          <StatsCard stats={stats} />
        )}
      </section>

      {/* Today's steps */}
      {loadingState === 'ready' && (
        <section>
          <TodaySteps onStatsUpdate={reloadStats} />
        </section>
      )}

      {/* Stuck button */}
      {loadingState === 'ready' && (
        <section>
          <button
            className="w-full p-4 bg-gradient-to-r from-orange-500 to-red-500 text-white rounded-xl font-semibold shadow-md hover:shadow-lg transition-all"
            onClick={() => {
              hapticFeedback('medium');
              window.location.href = '/stuck';
            }}
          >
            <div className="flex items-center justify-center gap-2">
              <span className="text-2xl">🆘</span>
              <span>Застрял? Получить микро-удар!</span>
            </div>
          </button>
        </section>
      )}

      {/* Goals list */}
      <section>
        <h2 className="text-lg font-semibold mb-3">🎯 Цели</h2>
        {loadingState === 'loading' || !goals ? (
          <div className="space-y-3">
            <GoalCardSkeleton />
            <GoalCardSkeleton />
          </div>
        ) : (
          <GoalsList
            goals={goals.goals}
            onGoalClick={(id) => {
              hapticFeedback('light');
              window.location.href = `/goals/${id}`;
            }}
          />
        )}
      </section>

      {/* Footer */}
      <footer className="text-center py-4">
        <p className="text-xs hint-text">
          Antipanic Bot • Превращай большие цели в маленькие шаги
        </p>
      </footer>
    </div>
  );
}
