'use client';

import type { Step } from '@/lib/api';

interface StepItemProps {
  step: Step;
  onComplete?: (stepId: number) => void;
  onSkip?: (stepId: number) => void;
}

export function StepItem({ step, onComplete, onSkip }: StepItemProps) {
  const difficultyConfig = getDifficultyConfig(step.difficulty);
  const statusConfig = getStatusConfig(step.status);
  
  return (
    <div className="card">
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-base">{statusConfig.emoji}</span>
            <h4 className="font-medium text-sm flex-1 truncate">
              {step.title}
            </h4>
          </div>
          
          <div className="flex items-center gap-2 mt-2">
            <span className={`text-xs px-2 py-0.5 rounded-full ${difficultyConfig.className}`}>
              {difficultyConfig.label}
            </span>
            <span className="text-xs hint-text">
              {step.estimated_minutes} мин
            </span>
            <span className="text-xs text-yellow-600">
              +{step.xp_reward} XP
            </span>
          </div>
        </div>
        
        {/* AICODE-NOTE: Action buttons will be implemented in phase 5.3 */}
        {step.status === 'pending' && (onComplete || onSkip) && (
          <div className="flex flex-col gap-2">
            {onComplete && (
              <button
                className="text-xs px-3 py-1.5 rounded-lg bg-green-500 text-white active:scale-95 transition-transform"
                onClick={() => onComplete(step.id)}
              >
                ✓ Сделал
              </button>
            )}
            {onSkip && (
              <button
                className="text-xs px-3 py-1.5 rounded-lg bg-gray-300 text-gray-700 active:scale-95 transition-transform"
                onClick={() => onSkip(step.id)}
              >
                Пропустить
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function getDifficultyConfig(difficulty: string): {
  label: string;
  className: string;
} {
  switch (difficulty) {
    case 'easy':
      return {
        label: 'Легко',
        className: 'bg-green-100 text-green-700',
      };
    case 'medium':
      return {
        label: 'Средне',
        className: 'bg-yellow-100 text-yellow-700',
      };
    case 'hard':
      return {
        label: 'Сложно',
        className: 'bg-red-100 text-red-700',
      };
    default:
      return {
        label: difficulty,
        className: 'bg-gray-100 text-gray-600',
      };
  }
}

function getStatusConfig(status: string): {
  emoji: string;
} {
  switch (status) {
    case 'pending':
      return { emoji: '⏸️' };
    case 'completed':
      return { emoji: '✅' };
    case 'skipped':
      return { emoji: '⏭️' };
    default:
      return { emoji: '📋' };
  }
}

export function StepItemSkeleton() {
  return (
    <div className="card">
      <div className="flex items-start gap-3">
        <div className="flex-1 space-y-2">
          <div className="skeleton h-5 w-3/4 rounded" />
          <div className="flex gap-2">
            <div className="skeleton h-5 w-16 rounded-full" />
            <div className="skeleton h-5 w-16 rounded" />
            <div className="skeleton h-5 w-16 rounded" />
          </div>
        </div>
      </div>
    </div>
  );
}

