'use client';

interface ProgressBarProps {
  progress: number; // 0-100
  height?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  animated?: boolean;
  color?: 'blue' | 'green' | 'yellow' | 'gray';
}

export function ProgressBar({
  progress,
  height = 'md',
  showLabel = true,
  animated = false,
  color = 'blue',
}: ProgressBarProps) {
  const clampedProgress = Math.max(0, Math.min(100, progress));
  
  const heightClasses = {
    sm: 'h-1.5',
    md: 'h-2.5',
    lg: 'h-4',
  };
  
  const colorClasses = {
    blue: 'bg-blue-500',
    green: 'bg-green-500',
    yellow: 'bg-yellow-500',
    gray: 'bg-gray-400',
  };
  
  return (
    <div className="w-full">
      <div className={`w-full ${heightClasses[height]} bg-gray-200 rounded-full overflow-hidden`}>
        <div
          className={`${heightClasses[height]} ${colorClasses[color]} rounded-full transition-all duration-500 ${animated ? 'animate-progress-pulse' : ''}`}
          style={{ width: `${clampedProgress}%` }}
        />
      </div>
      {showLabel && (
        <div className="text-xs hint-text text-right mt-1">
          {clampedProgress}%
        </div>
      )}
    </div>
  );
}

