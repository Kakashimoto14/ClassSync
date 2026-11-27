import type { DailyShapeRules } from '../../../../packages/shared-types/src/scheduling';

export type PatternPolicy = 'single' | 'split' | 'flexible';

/** Owner-authorized starting preferences; the same values new periods receive. */
export const COMMUTER_DEFAULTS: DailyShapeRules = {
  min_sessions_per_active_day: 2,
  max_sessions_per_day: 4,
  max_daily_span_minutes: 540,
};
