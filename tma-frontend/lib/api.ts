/**
 * FastAPI client for Antipanic Bot TMA
 */

import { getInitData } from './telegram';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Base fetch wrapper with authentication
 */
async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const initData = getInitData();

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(initData && { 'X-Telegram-Init-Data': initData }),
    ...options.headers,
  };

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: `HTTP ${response.status}`,
    }));
    throw new Error(error.detail || 'API request failed');
  }

  return response.json();
}

// API Types
export interface User {
  telegram_id: number;
  username: string | null;
  first_name: string;
  xp: number;
  level: number;
  streak_days: number;
  timezone_offset: number;
}

export interface MicrohitOption {
  index: number;
  text: string;
}

export interface MicrohitGenerateResponse {
  options: MicrohitOption[];
  step_id: number;
}

export interface MicrohitCompleteResponse {
  xp_earned: number;
  total_xp: number;
  streak_days: number;
  level: number;
}

// API Methods

/**
 * Get current user profile
 */
export async function getMe(): Promise<User> {
  return apiFetch<User>('/api/me');
}

/**
 * Generate microhit options
 */
export async function generateMicrohit(data: {
  step_title: string;
  blocker_type: 'fear' | 'overwhelm' | 'unclear' | 'boring' | 'distraction';
  details?: string;
}): Promise<MicrohitGenerateResponse> {
  return apiFetch<MicrohitGenerateResponse>('/api/microhit/generate', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Complete a microhit step
 */
export async function completeMicrohit(
  stepId: number
): Promise<MicrohitCompleteResponse> {
  return apiFetch<MicrohitCompleteResponse>('/api/microhit/complete', {
    method: 'POST',
    body: JSON.stringify({ step_id: stepId }),
  });
}
