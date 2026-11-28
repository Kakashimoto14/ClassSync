import { meterTone, type MeterTone } from './meter-tone';
import './meter.css';

const TONE_LABELS: Record<MeterTone, string> = {
  ok: 'within range',
  high: 'high',
  over: 'over the limit',
};

/** Horizontal utilization or load bar. `null` means the figure cannot be calculated. */
export function Meter({
  label,
  value,
  high = 70,
  over = 90,
}: {
  label: string;
  value: number | null;
  high?: number;
  over?: number;
}) {
  if (value === null) return <span className="meter meter--empty">Not available</span>;
  const tone = meterTone(value, high, over);
  const width = Math.max(0, Math.min(100, value));
  return (
    <span
      className={`meter meter--${tone}`}
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={Math.max(100, value)}
      aria-valuenow={value}
      aria-valuetext={`${value}%, ${TONE_LABELS[tone]}`}
    >
      <span className="meter__track" aria-hidden="true">
        <span className="meter__fill" style={{ width: `${width}%` }} />
      </span>
      <span className="meter__value">{value}%</span>
      {/* Colour is never the only signal. */}
      <span className="meter__tone" aria-hidden="true">
        {tone === 'ok' ? '' : tone === 'high' ? 'High' : 'Over'}
      </span>
    </span>
  );
}
