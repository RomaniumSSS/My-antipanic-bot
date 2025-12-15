/**
 * API client for Antipanic Bot backend.
 * 
 * All requests include Telegram initData for authentication.
 */

import { getInitData } from './telegram';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ============ Types (matching backend schemas) ============

export interface User {
  telegram_id: number;
  username: string | null;
  first_name: string | null;
  xp: number;
  level: number;
  streak_days: number;
  reminder_morning: string;
  reminder_evening: string;
  timezone_offset: number;
  reminders_enabled: boolean;
}

export interface Stage {
  id: number;
  title: string;
  order: number;
  start_date: string;
  end_date: string;
  progress: number;
  status: string;
}

export interface GoalListItem {
  id: number;
  title: string;
  deadline: string;
  status: string;
  created_at: string;
}

export interface GoalDetail {
  id: number;
  title: string;
  description: string | null;
  start_date: string;
  deadline: string;
  status: string;
  stages: Stage[];
}

export interface GoalsListResponse {
  goals: GoalListItem[];
  total: number;
}

export interface Stats {
  xp: number;
  level: number;
  xp_to_next_level: number;
  streak_days: number;
  total_goals: number;
  active_goals: number;
  completed_goals: number;
  total_steps_completed: number;
  steps_today: number;
  completion_rate: number;
}

export interface Step {
  id: number;
  title: string;
  difficulty: string;
  estimated_minutes: number;
  xp_reward: number;
  scheduled_date: string | null;
  status: string;
}

export interface TodayStepsResponse {
  steps: Step[];
  total_assigned: number;
  completed: number;
}

export interface MicroHitResponse {
  micro_action: string;
  original_step: Step;
  estimated_minutes: number;
}

// ============ API Error ============

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    message?: string
  ) {
    super(message || `API Error: ${status} ${statusText}`);
    this.name = 'ApiError';
  }
}

// ============ Fetch wrapper ============

async function fetchAPI<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const initData = getInitData();
  
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };
  
  // Add auth header if we have initData (running in Telegram)
  if (initData) {
    headers['Authorization'] = `tma ${initData}`;
  }
  
  const url = `${API_URL}${endpoint}`;
  
  if (process.env.NEXT_PUBLIC_DEBUG === 'true') {
    console.log(`[API] ${options.method || 'GET'} ${url}`);
  }
  
  const response = await fetch(url, {
    ...options,
    headers,
  });
  
  if (!response.ok) {
    const errorText = await response.text().catch(() => '');
    throw new ApiError(response.status, response.statusText, errorText);
  }
  
  return response.json();
}

// ============ API Methods ============

/**
 * Get current user profile.
 * Creates user if not exists (based on Telegram initData).
 */
export async function getMe(): Promise<User> {
  return fetchAPI<User>('/api/me');
}

/**
 * Get user statistics.
 */
export async function getStats(): Promise<Stats> {
  return fetchAPI<Stats>('/api/stats');
}

/**
 * Get list of user's goals.
 */
export async function getGoals(): Promise<GoalsListResponse> {
  return fetchAPI<GoalsListResponse>('/api/goals');
}

/**
 * Get goal details with stages.
 */
export async function getGoal(id: number): Promise<GoalDetail> {
  return fetchAPI<GoalDetail>(`/api/goals/${id}`);
}

/**
 * Get today's assigned steps.
 */
export async function getTodaySteps(): Promise<TodayStepsResponse> {
  return fetchAPI<TodayStepsResponse>('/api/steps/today');
}

/**
 * Generate micro-action for a step.
 */
export async function generateMicroHit(stepId: number, blockerText?: string): Promise<MicroHitResponse> {
  return fetchAPI<MicroHitResponse>('/api/microhit', {
    method: 'POST',
    body: JSON.stringify({
      step_id: stepId,
      blocker_text: blockerText,
    }),
  });
}
