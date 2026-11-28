export type MeterTone = 'ok' | 'high' | 'over';

/** Green below `high`, amber from `high`, red above `over`. */
export function meterTone(value: number, high: number, over: number): MeterTone {
  return value > over ? 'over' : value >= high ? 'high' : 'ok';
}
