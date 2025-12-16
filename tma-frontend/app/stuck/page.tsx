'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTelegram } from '@/app/providers';
import {
  getTodaySteps,
  generateMicroHit,
  completeStep,
  type TodayStepsResponse,
  type MicroHitResponse,
  type MicroHitVariant,
} from '@/lib/api';
import { hapticFeedback } from '@/lib/telegram';

type LoadingState = 'loading' | 'ready' | 'error';
type FlowState = 'select_step' | 'select_blocker' | 'enter_details' | 'show_variants' | 'done';

interface BlockerOption {
  type: string;
  emoji: string;
  label: string;
  description: string;
}

const BLOCKERS: BlockerOption[] = [
  { type: 'fear', emoji: '😨', label: 'Страшно', description: 'Тревожно браться за задачу' },
  { type: 'unclear', emoji: '🤷', label: 'Не знаю с чего', description: 'Непонятно как начать' },
  { type: 'no_time', emoji: '⏰', label: 'Нет времени', description: 'Кажется что времени мало' },
  { type: 'no_energy', emoji: '😴', label: 'Нет сил', description: 'Энергия на нуле' },
];

export default function StuckPage() {
  const router = useRouter();
  const { isReady, isInTelegram } = useTelegram();

  const [loadingState, setLoadingState] = useState<LoadingState>('loading');
  const [flowState, setFlowState] = useState<FlowState>('select_step');
  const [error, setError] = useState<string | null>(null);

  // Data states
  const [todaySteps, setTodaySteps] = useState<TodayStepsResponse | null>(null);
  const [selectedStepId, setSelectedStepId] = useState<number | null>(null);
  const [selectedBlocker, setSelectedBlocker] = useState<string | null>(null);
  const [blockerDetails, setBlockerDetails] = useState<string>('');
  const [microhitResponse, setMicrohitResponse] = useState<MicroHitResponse | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  // Load today's steps on mount
  useEffect(() => {
    if (!isReady || !isInTelegram) return;

    async function loadSteps() {
      try {
        const data = await getTodaySteps();
        setTodaySteps(data);
        setLoadingState('ready');

        // Auto-select first pending step if available
        const firstPending = data.steps.find((s) => s.status === 'pending');
        if (firstPending) {
          setSelectedStepId(firstPending.id);
        }

        hapticFeedback('success');
      } catch (err) {
        console.error('Failed to load steps:', err);
        setError('Не удалось загрузить шаги');
        setLoadingState('error');
        hapticFeedback('error');
      }
    }

    loadSteps();
  }, [isReady, isInTelegram]);

  // Generate microhit variants
  const handleGenerateMicrohits = async () => {
    if (!selectedStepId || !selectedBlocker) return;

    setIsGenerating(true);
    hapticFeedback('light');

    try {
      const response = await generateMicroHit(
        selectedStepId,
        selectedBlocker,
        blockerDetails || undefined
      );
      setMicrohitResponse(response);
      setFlowState('show_variants');
      hapticFeedback('success');
    } catch (err) {
      console.error('Failed to generate microhits:', err);
      setError('Не удалось сгенерировать варианты');
      hapticFeedback('error');
    } finally {
      setIsGenerating(false);
    }
  };

  // Handle blocker selection
  const handleBlockerSelect = (blockerType: string) => {
    setSelectedBlocker(blockerType);
    hapticFeedback('light');

    // For "unclear" blocker, show details input
    if (blockerType === 'unclear') {
      setFlowState('enter_details');
    } else {
      // Generate immediately for other blockers
      setFlowState('enter_details'); // Still show details option
    }
  };

  // Handle variant selection (user picks one)
  const handleVariantSelect = (variant: MicroHitVariant) => {
    hapticFeedback('success');
    setFlowState('done');
  };

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
  if (loadingState === 'loading') {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <div className="text-4xl mb-4 animate-pulse">🤔</div>
        <p className="hint-text">Загрузка...</p>
      </div>
    );
  }

  const pendingSteps = todaySteps?.steps.filter((s) => s.status === 'pending') || [];
  const selectedStep = todaySteps?.steps.find((s) => s.id === selectedStepId);
  const selectedBlockerData = BLOCKERS.find((b) => b.type === selectedBlocker);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <button
          className="text-2xl hover:opacity-70"
          onClick={() => router.back()}
        >
          ←
        </button>
        <h1 className="text-2xl font-bold">🆘 Застрял?</h1>
      </div>

      {/* Step 1: Select Step */}
      {flowState === 'select_step' && (
        <div className="space-y-4">
          <div className="card">
            <h2 className="text-lg font-semibold mb-3">Выбери шаг, на котором застрял:</h2>
            
            {pendingSteps.length === 0 ? (
              <div className="text-center py-8">
                <div className="text-4xl mb-3">✅</div>
                <p className="hint-text mb-4">
                  У тебя нет незавершённых шагов на сегодня!
                </p>
                <button className="btn-primary" onClick={() => router.push('/')}>
                  Вернуться на главную
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                {pendingSteps.map((step) => (
                  <button
                    key={step.id}
                    className={`w-full p-4 rounded-lg border-2 transition-all text-left ${
                      selectedStepId === step.id
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                    onClick={() => {
                      setSelectedStepId(step.id);
                      hapticFeedback('light');
                    }}
                  >
                    <div className="font-medium">{step.title}</div>
                    <div className="text-sm hint-text mt-1">
                      ~{step.estimated_minutes} мин • {step.xp_reward} XP
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {selectedStepId && (
            <button
              className="btn-primary w-full"
              onClick={() => {
                setFlowState('select_blocker');
                hapticFeedback('light');
              }}
            >
              Дальше →
            </button>
          )}
        </div>
      )}

      {/* Step 2: Select Blocker */}
      {flowState === 'select_blocker' && (
        <div className="space-y-4">
          <div className="card bg-gray-50">
            <div className="text-sm text-gray-600 mb-1">Шаг:</div>
            <div className="font-medium">{selectedStep?.title}</div>
          </div>

          <div className="card">
            <h2 className="text-lg font-semibold mb-3">🆘 Что мешает двигаться?</h2>
            
            <div className="grid grid-cols-2 gap-3">
              {BLOCKERS.map((blocker) => (
                <button
                  key={blocker.type}
                  className="p-4 rounded-lg border-2 border-gray-200 hover:border-gray-300 transition-all text-left"
                  onClick={() => handleBlockerSelect(blocker.type)}
                >
                  <div className="text-3xl mb-2">{blocker.emoji}</div>
                  <div className="font-medium text-sm mb-1">{blocker.label}</div>
                  <div className="text-xs hint-text">{blocker.description}</div>
                </button>
              ))}
            </div>
          </div>

          <button
            className="btn-secondary w-full"
            onClick={() => setFlowState('select_step')}
          >
            ← Назад
          </button>
        </div>
      )}

      {/* Step 3: Enter Details (Optional) */}
      {flowState === 'enter_details' && (
        <div className="space-y-4">
          <div className="card bg-gray-50">
            <div className="text-sm text-gray-600 mb-1">Шаг:</div>
            <div className="font-medium mb-3">{selectedStep?.title}</div>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-2xl">{selectedBlockerData?.emoji}</span>
              <span className="text-gray-600">{selectedBlockerData?.label}</span>
            </div>
          </div>

          <div className="card">
            <h2 className="text-lg font-semibold mb-3">
              {selectedBlocker === 'unclear'
                ? 'Что именно непонятно?'
                : 'Хочешь уточнить?'}
            </h2>
            
            <textarea
              className="w-full p-3 border rounded-lg resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              rows={4}
              placeholder={
                selectedBlocker === 'unclear'
                  ? 'Напиши, что именно непонятно (или "-" чтобы пропустить)'
                  : 'Опционально: уточни детали'
              }
              value={blockerDetails}
              onChange={(e) => setBlockerDetails(e.target.value)}
            />

            <div className="mt-3 text-xs hint-text">
              💡 Детали помогут получить более точные рекомендации
            </div>
          </div>

          <button
            className="btn-primary w-full"
            onClick={handleGenerateMicrohits}
            disabled={isGenerating}
          >
            {isGenerating ? (
              <span className="flex items-center justify-center gap-2">
                <span className="animate-spin">⚙️</span>
                Генерирую варианты...
              </span>
            ) : (
              'Получить микро-удары →'
            )}
          </button>

          <button
            className="btn-secondary w-full"
            onClick={() => setFlowState('select_blocker')}
            disabled={isGenerating}
          >
            ← Назад
          </button>
        </div>
      )}

      {/* Step 4: Show Variants */}
      {flowState === 'show_variants' && microhitResponse && (
        <div className="space-y-4">
          <div className="card bg-gray-50">
            <div className="text-sm text-gray-600 mb-1">Шаг:</div>
            <div className="font-medium mb-3">{microhitResponse.original_step.title}</div>
            <div className="flex items-center gap-2 text-sm">
              <span className="text-2xl">{selectedBlockerData?.emoji}</span>
              <span className="text-gray-600">{selectedBlockerData?.label}</span>
            </div>
          </div>

          <div className="card">
            <h2 className="text-lg font-semibold mb-3">
              {selectedBlockerData?.emoji} Варианты микро-ударов:
            </h2>
            
            <div className="space-y-3">
              {microhitResponse.variants.map((variant) => (
                <button
                  key={variant.index}
                  className="w-full p-4 rounded-lg border-2 border-gray-200 hover:border-blue-500 hover:bg-blue-50 transition-all text-left"
                  onClick={() => handleVariantSelect(variant)}
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center font-bold">
                      {variant.index}
                    </div>
                    <div className="flex-1">
                      <p className="text-sm leading-relaxed">{variant.text}</p>
                    </div>
                  </div>
                </button>
              ))}
            </div>

            <div className="mt-4 text-xs hint-text">
              💡 Выбери наиболее подходящий вариант — всего 2-5 минут!
            </div>
          </div>

          <button
            className="btn-secondary w-full"
            onClick={() => {
              setFlowState('enter_details');
              setMicrohitResponse(null);
            }}
          >
            🔄 Генерировать новые варианты
          </button>
        </div>
      )}

      {/* Step 5: Done */}
      {flowState === 'done' && (
        <div className="space-y-4">
          <div className="card text-center">
            <div className="text-6xl mb-4">🔥</div>
            <h2 className="text-xl font-bold mb-2">Отлично!</h2>
            <p className="text-gray-600 mb-4">
              Действуй прямо сейчас. Всего 2-5 минут.
            </p>
            <p className="text-sm hint-text">
              Когда сделаешь — отмечай на главной странице
            </p>
          </div>

          <button
            className="btn-primary w-full"
            onClick={() => router.push('/')}
          >
            Вернуться на главную
          </button>

          <button
            className="btn-secondary w-full"
            onClick={() => {
              setFlowState('select_blocker');
              setMicrohitResponse(null);
            }}
          >
            Получить ещё подсказку
          </button>
        </div>
      )}
    </div>
  );
}

