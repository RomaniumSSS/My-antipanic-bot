'use client';

/**
 * TodaySteps component - displays today's assigned steps with action buttons.
 * 
 * Features:
 * - Displays steps scheduled for today
 * - Complete/Skip actions with haptic feedback
 * - Real-time updates after actions
 * - Shows XP rewards and difficulty
 */

import { useState, useEffect } from 'react';
import { getTodaySteps, completeStep, skipStep, type Step, type CompleteStepResponse } from '@/lib/api';

interface TodayStepsProps {
  onStatsUpdate?: () => void; // Callback to refresh stats after action
}

export default function TodaySteps({ onStatsUpdate }: TodayStepsProps) {
  const [steps, setSteps] = useState<Step[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionInProgress, setActionInProgress] = useState<number | null>(null);
  const [completionMessage, setCompletionMessage] = useState<string | null>(null);

  useEffect(() => {
    loadSteps();
  }, []);

  async function loadSteps() {
    try {
      setLoading(true);
      setError(null);
      const data = await getTodaySteps();
      setSteps(data.steps);
    } catch (err) {
      console.error('Failed to load today steps:', err);
      setError('Не удалось загрузить шаги');
    } finally {
      setLoading(false);
    }
  }

  async function handleComplete(stepId: number) {
    if (actionInProgress) return;

    try {
      setActionInProgress(stepId);
      
      // Haptic feedback
      if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
      }

      const result: CompleteStepResponse = await completeStep(stepId);

      // Show success message with XP
      setCompletionMessage(
        `✅ +${result.xp_earned} XP${result.streak_updated ? ` | 🔥 ${result.new_streak} дней` : ''}`
      );

      // Update local state
      setSteps(prev => prev.map(s => 
        s.id === stepId ? { ...s, status: 'completed' } : s
      ));

      // Refresh stats
      if (onStatsUpdate) {
        onStatsUpdate();
      }

      // Clear message after 3 seconds
      setTimeout(() => setCompletionMessage(null), 3000);
    } catch (err) {
      console.error('Failed to complete step:', err);
      setError('Не удалось выполнить шаг');
      
      if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.notificationOccurred('error');
      }
    } finally {
      setActionInProgress(null);
    }
  }

  async function handleSkip(stepId: number) {
    if (actionInProgress) return;

    try {
      setActionInProgress(stepId);
      
      // Haptic feedback
      if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
      }

      await skipStep(stepId, 'Не подошло');

      // Update local state
      setSteps(prev => prev.map(s => 
        s.id === stepId ? { ...s, status: 'skipped' } : s
      ));

      // Refresh stats
      if (onStatsUpdate) {
        onStatsUpdate();
      }
    } catch (err) {
      console.error('Failed to skip step:', err);
      setError('Не удалось пропустить шаг');
      
      if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.notificationOccurred('error');
      }
    } finally {
      setActionInProgress(null);
    }
  }

  function getDifficultyColor(difficulty: string): string {
    switch (difficulty) {
      case 'easy': return 'bg-green-500/20 text-green-400';
      case 'medium': return 'bg-yellow-500/20 text-yellow-400';
      case 'hard': return 'bg-red-500/20 text-red-400';
      default: return 'bg-gray-500/20 text-gray-400';
    }
  }

  function getDifficultyLabel(difficulty: string): string {
    switch (difficulty) {
      case 'easy': return 'Легко';
      case 'medium': return 'Средне';
      case 'hard': return 'Сложно';
      default: return difficulty;
    }
  }

  if (loading) {
    return (
      <div className="bg-white/5 backdrop-blur-sm rounded-2xl p-6">
        <h2 className="text-xl font-bold text-white mb-4">📋 Шаги на сегодня</h2>
        <div className="text-center text-gray-400 py-8">
          <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto"></div>
        </div>
      </div>
    );
  }

  const pendingSteps = steps.filter(s => s.status === 'pending');
  const completedCount = steps.filter(s => s.status === 'completed').length;

  return (
    <div className="bg-white/5 backdrop-blur-sm rounded-2xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-white">📋 Шаги на сегодня</h2>
        {steps.length > 0 && (
          <div className="text-sm text-gray-400">
            {completedCount} / {steps.length}
          </div>
        )}
      </div>

      {completionMessage && (
        <div className="mb-4 bg-green-500/20 text-green-400 rounded-xl p-3 text-center font-medium animate-fade-in">
          {completionMessage}
        </div>
      )}

      {error && (
        <div className="mb-4 bg-red-500/20 text-red-400 rounded-xl p-3 text-center">
          {error}
        </div>
      )}

      {steps.length === 0 ? (
        <div className="text-center text-gray-400 py-8">
          <p className="mb-2">🎯 Шагов на сегодня нет</p>
          <p className="text-sm">Начни утреннюю сессию в боте</p>
        </div>
      ) : pendingSteps.length === 0 ? (
        <div className="text-center text-green-400 py-8">
          <p className="text-3xl mb-2">🎉</p>
          <p className="font-bold">Все шаги выполнены!</p>
          <p className="text-sm text-gray-400 mt-2">Отличная работа сегодня</p>
        </div>
      ) : (
        <div className="space-y-3">
          {steps.map((step) => (
            <div
              key={step.id}
              className={`
                bg-white/5 rounded-xl p-4 border border-white/10
                ${step.status === 'completed' ? 'opacity-50' : ''}
                ${step.status === 'skipped' ? 'opacity-30' : ''}
                transition-all
              `}
            >
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="flex-1">
                  <p className="text-white font-medium leading-tight mb-2">
                    {step.status === 'completed' && '✅ '}
                    {step.status === 'skipped' && '⏭️ '}
                    {step.title}
                  </p>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`text-xs px-2 py-1 rounded-full ${getDifficultyColor(step.difficulty)}`}>
                      {getDifficultyLabel(step.difficulty)}
                    </span>
                    <span className="text-xs text-gray-400">
                      ⏱️ {step.estimated_minutes} мин
                    </span>
                    <span className="text-xs text-blue-400">
                      ✨ {step.xp_reward} XP
                    </span>
                  </div>
                </div>
              </div>

              {step.status === 'pending' && (
                <div className="flex gap-2">
                  <button
                    onClick={() => handleComplete(step.id)}
                    disabled={actionInProgress === step.id}
                    className="flex-1 bg-green-500 hover:bg-green-600 disabled:bg-green-500/50 
                             text-white font-medium py-2.5 px-4 rounded-xl 
                             transition-colors disabled:cursor-not-allowed"
                  >
                    {actionInProgress === step.id ? (
                      <span className="flex items-center justify-center gap-2">
                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      </span>
                    ) : (
                      '✓ Сделал'
                    )}
                  </button>
                  <button
                    onClick={() => handleSkip(step.id)}
                    disabled={actionInProgress === step.id}
                    className="flex-1 bg-gray-600 hover:bg-gray-700 disabled:bg-gray-600/50 
                             text-white font-medium py-2.5 px-4 rounded-xl 
                             transition-colors disabled:cursor-not-allowed"
                  >
                    ⏭️ Пропустить
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


