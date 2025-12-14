'use client';

import { useEffect, useState } from 'react';
import {
  initTelegramWebApp,
  getTelegramUser,
  isTelegramWebApp,
} from '@/lib/telegram';
import {
  getMe,
  generateMicrohit,
  completeMicrohit,
  type User,
  type MicrohitOption,
} from '@/lib/api';

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Microhit state
  const [stepTitle, setStepTitle] = useState('');
  const [blockerType, setBlockerType] = useState<'fear' | 'overwhelm' | 'unclear' | 'boring' | 'distraction'>('fear');
  const [microhitOptions, setMicrohitOptions] = useState<MicrohitOption[]>([]);
  const [currentStepId, setCurrentStepId] = useState<number | null>(null);
  const [generating, setGenerating] = useState(false);
  const [completing, setCompleting] = useState(false);

  useEffect(() => {
    // Initialize Telegram WebApp
    const webApp = initTelegramWebApp();

    if (!isTelegramWebApp()) {
      setError('This app only works inside Telegram');
      setLoading(false);
      return;
    }

    // Load user profile
    loadUser();
  }, []);

  const loadUser = async () => {
    try {
      setLoading(true);
      const userData = await getMe();
      setUser(userData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load profile');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateMicrohit = async () => {
    if (!stepTitle.trim()) {
      setError('Please enter a task description');
      return;
    }

    try {
      setGenerating(true);
      setError(null);
      const result = await generateMicrohit({
        step_title: stepTitle,
        blocker_type: blockerType,
      });
      setMicrohitOptions(result.options);
      setCurrentStepId(result.step_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate microhits');
    } finally {
      setGenerating(false);
    }
  };

  const handleCompleteMicrohit = async () => {
    if (!currentStepId) return;

    try {
      setCompleting(true);
      setError(null);
      const result = await completeMicrohit(currentStepId);

      // Update user XP
      if (user) {
        setUser({
          ...user,
          xp: result.total_xp,
          level: result.level,
          streak_days: result.streak_days,
        });
      }

      // Clear microhit state
      setMicrohitOptions([]);
      setCurrentStepId(null);
      setStepTitle('');

      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to complete microhit');
    } finally {
      setCompleting(false);
    }
  };

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center p-4">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-hint-color">Loading...</p>
        </div>
      </main>
    );
  }

  if (error && !user) {
    return (
      <main className="min-h-screen flex items-center justify-center p-4">
        <div className="text-center">
          <p className="text-red-500 mb-4">{error}</p>
          <button
            onClick={loadUser}
            className="px-4 py-2 bg-primary text-primary-text rounded-lg"
          >
            Retry
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen p-4 pb-20">
      {/* Profile Section */}
      {user && (
        <div className="mb-8 p-4 bg-secondary-bg rounded-lg">
          <h1 className="text-2xl font-bold mb-2">
            {user.first_name}
            {user.username && <span className="text-hint-color ml-2">@{user.username}</span>}
          </h1>
          <div className="flex gap-4 text-sm">
            <div>
              <span className="text-hint-color">Level:</span>{' '}
              <span className="font-semibold">{user.level}</span>
            </div>
            <div>
              <span className="text-hint-color">XP:</span>{' '}
              <span className="font-semibold">{user.xp}</span>
            </div>
            <div>
              <span className="text-hint-color">Streak:</span>{' '}
              <span className="font-semibold">{user.streak_days} days</span>
            </div>
          </div>
        </div>
      )}

      {/* Microhit Generator */}
      <div className="mb-6">
        <h2 className="text-xl font-bold mb-4">Generate Micro-Action</h2>

        {error && (
          <div className="mb-4 p-3 bg-red-100 text-red-700 rounded-lg">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              What task are you stuck on?
            </label>
            <input
              type="text"
              value={stepTitle}
              onChange={(e) => setStepTitle(e.target.value)}
              placeholder="e.g., Write the first paragraph"
              className="w-full px-3 py-2 border border-hint-color rounded-lg bg-bg-color text-text-color"
              disabled={generating || microhitOptions.length > 0}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              What&apos;s blocking you?
            </label>
            <select
              value={blockerType}
              onChange={(e) => setBlockerType(e.target.value as any)}
              className="w-full px-3 py-2 border border-hint-color rounded-lg bg-bg-color text-text-color"
              disabled={generating || microhitOptions.length > 0}
            >
              <option value="fear">Fear / Anxiety</option>
              <option value="overwhelm">Overwhelmed</option>
              <option value="unclear">Unclear what to do</option>
              <option value="boring">Boring / Unmotivated</option>
              <option value="distraction">Distracted</option>
            </select>
          </div>

          {microhitOptions.length === 0 ? (
            <button
              onClick={handleGenerateMicrohit}
              disabled={generating || !stepTitle.trim()}
              className="w-full px-4 py-3 bg-primary text-primary-text rounded-lg font-medium disabled:opacity-50"
            >
              {generating ? 'Generating...' : 'Generate Micro-Actions'}
            </button>
          ) : (
            <>
              <div className="space-y-2">
                <p className="text-sm font-medium">Choose a micro-action to start:</p>
                {microhitOptions.map((option) => (
                  <div
                    key={option.index}
                    className="p-3 bg-secondary-bg rounded-lg border border-hint-color"
                  >
                    <span className="font-semibold">{option.index + 1}.</span> {option.text}
                  </div>
                ))}
              </div>

              <div className="flex gap-2">
                <button
                  onClick={handleCompleteMicrohit}
                  disabled={completing}
                  className="flex-1 px-4 py-3 bg-green-600 text-white rounded-lg font-medium disabled:opacity-50"
                >
                  {completing ? 'Completing...' : 'I Did It! +XP'}
                </button>
                <button
                  onClick={handleGenerateMicrohit}
                  disabled={generating}
                  className="px-4 py-3 bg-secondary-bg text-text-color rounded-lg font-medium"
                >
                  More Options
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </main>
  );
}
