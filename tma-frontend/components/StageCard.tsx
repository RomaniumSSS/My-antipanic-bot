'use client';

import { ProgressBar } from './ProgressBar';
import type { Stage } from '@/lib/api';

interface StageCardProps {
  stage: Stage;
  isActive?: boolean;
}

export function StageCard({ stage, isActive = false }: StageCardProps) {
  const statusConfig = getStageStatusConfig(stage.status);
  const dateRange = formatDateRange(stage.start_date, stage.end_date);
  
  return (
    <div
      className={`card ${isActive ? 'border-2 border-blue-500' : ''} transition-all`}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xl">{statusConfig.emoji}</span>
            <h3 className="font-semibold text-base truncate">
              {stage.title}
            </h3>
            {isActive && (
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                Текущий
              </span>
            )}
          </div>
          <div className="text-xs hint-text">
            {dateRange}
          </div>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full ${statusConfig.className}`}>
          {statusConfig.label}
        </span>
      </div>
      
      <ProgressBar
        progress={stage.progress}
        color={statusConfig.progressColor}
        animated={isActive && stage.progress > 0 && stage.progress < 100}
      />
    </div>
  );
}

function getStageStatusConfig(status: string): {
  label: string;
  emoji: string;
  className: string;
  progressColor: 'blue' | 'green' | 'yellow' | 'gray';
} {
  switch (status) {
    case 'active':
      return {
        label: 'В работе',
        emoji: '🎯',
        className: 'bg-blue-100 text-blue-700',
        progressColor: 'blue',
      };
    case 'completed':
      return {
        label: 'Завершён',
        emoji: '✅',
        className: 'bg-green-100 text-green-700',
        progressColor: 'green',
      };
    case 'pending':
      return {
        label: 'Ожидает',
        emoji: '⏳',
        className: 'bg-gray-100 text-gray-600',
        progressColor: 'gray',
      };
    default:
      return {
        label: status,
        emoji: '📋',
        className: 'bg-gray-100 text-gray-600',
        progressColor: 'gray',
      };
  }
}

function formatDateRange(startDate: string, endDate: string): string {
  try {
    const start = new Date(startDate);
    const end = new Date(endDate);
    
    const formatOptions: Intl.DateTimeFormatOptions = {
      day: 'numeric',
      month: 'short',
    };
    
    const startStr = start.toLocaleDateString('ru-RU', formatOptions);
    const endStr = end.toLocaleDateString('ru-RU', formatOptions);
    
    return `${startStr} — ${endStr}`;
  } catch {
    return 'Даты не указаны';
  }
}

export function StageCardSkeleton() {
  return (
    <div className="card">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 space-y-2">
          <div className="skeleton h-6 w-3/4 rounded" />
          <div className="skeleton h-4 w-1/2 rounded" />
        </div>
        <div className="skeleton h-5 w-16 rounded-full" />
      </div>
      <div className="skeleton h-2.5 w-full rounded-full" />
    </div>
  );
}

