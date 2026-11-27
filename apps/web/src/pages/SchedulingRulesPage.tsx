import { useEffect, useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { ClassSyncSkeleton } from '../components/loading/ClassSyncLoading';
import {
  listAcademicPeriods,
  loadAcademicPeriod,
  saveAcademicRecord,
  type AcademicPeriod,
  type AcademicRecord,
  type AcademicSnapshot,
} from '../lib/academic-api';
import { periodLabel } from '../lib/workspace-context';
import { COMMUTER_DEFAULTS } from './commuter-rules';
import { PatternPolicySelect, ShapeRuleFields } from './SchedulingRuleFields';

type Constraints = Extract<AcademicRecord, { kind: 'constraints' }>;
const message = (failure: unknown, fallback: string) =>
  failure instanceof Error ? failure.message : fallback;

export function SchedulingRulesPage() {
  const [params, setParams] = useSearchParams();
  const period = params.get('period') ?? '';
  const [periods, setPeriods] = useState<AcademicPeriod[] | null>(null);
  const [snapshot, setSnapshot] = useState<AcademicSnapshot | null>(null);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let ignore = false;
    listAcademicPeriods()
      .then((value) => {
        if (!ignore) setPeriods(value.periods ?? []);
      })
      .catch((failure) => {
        if (!ignore) setError(message(failure, 'Academic periods could not be loaded.'));
      });
    return () => {
      ignore = true;
    };
  }, [reload]);

  useEffect(() => {
    let ignore = false;
    setSnapshot(null);
    if (!period) return;
    setError('');
    loadAcademicPeriod(period)
      .then((value) => {
        if (!ignore) setSnapshot(value);
      })
      .catch((failure) => {
        if (!ignore) setError(message(failure, 'This period could not be loaded.'));
      });
    return () => {
      ignore = true;
    };
  }, [period, reload]);

  return (
    <div>
      <div className="page-heading">
        <div>
          <h1>Institutional Scheduling Rules</h1>
          <p>Commuter-friendly day shape and 180-minute subject patterns, per academic period.</p>
        </div>
      </div>
      <section className="workspace-card">
        <label>
          Academic period
          <select
            value={period}
            onChange={(e) => setParams(e.target.value ? { period: e.target.value } : {})}
          >
            <option value="">Choose a period</option>
            {periods?.map((item) => (
              <option key={item.id} value={item.id}>
                {periodLabel(item)}
              </option>
            ))}
          </select>
        </label>
        {!periods && !error && <ClassSyncSkeleton layout="kpis" label="Loading academic periods" />}
        {periods?.length === 0 && (
          <p>
            <Link to="/admin/academic">Create an academic period</Link> before setting its rules.
          </p>
        )}
      </section>
      {error && (
        <div role="alert" className="workspace-card">
          <p>{error}</p>
          <Button
            variant="secondary"
            onClick={() => {
              setError('');
              setReload((n) => n + 1);
            }}
          >
            Retry
          </Button>
        </div>
      )}
      {period && !snapshot && !error && (
        <ClassSyncSkeleton layout="kpis" label="Loading scheduling rules" />
      )}
      {snapshot && (
        <RulesForm
          key={snapshot.period.id}
          snapshot={snapshot}
          onSaved={setSnapshot}
          onReload={() => setReload((n) => n + 1)}
        />
      )}
    </div>
  );
}

function RulesForm({
  snapshot,
  onSaved,
  onReload,
}: {
  snapshot: AcademicSnapshot;
  onSaved: (snapshot: AcademicSnapshot) => void;
  onReload: () => void;
}) {
  const existing = snapshot.records.find((item) => item.record.kind === 'constraints');
  const record = (existing?.record ?? { id: 'rules', kind: 'constraints' }) as Constraints;
  const [shape, setShape] = useState(record.daily_shape ?? null);
  const [policy, setPolicy] = useState(record.pattern_policy_180 ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError('');
    setSaved(false);
    try {
      const next = await saveAcademicRecord(snapshot.period.id, {
        expected_revision: existing?.revision ?? 0,
        record: { ...record, daily_shape: shape, pattern_policy_180: policy },
      });
      setSaved(true);
      onSaved(next);
    } catch (failure) {
      setError(message(failure, 'The rules were not saved.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="workspace-card academic-record-form"
      aria-label="Scheduling rules"
      aria-busy={busy}
      onSubmit={submit}
    >
      <fieldset disabled={busy} className="academic-form-fields">
        <ShapeRuleFields value={shape} onChange={setShape} />
        <PatternPolicySelect
          label="Default pattern for 180-minute subjects"
          emptyLabel="Use each subject's saved patterns"
          value={policy}
          onChange={setPolicy}
        />
        <p className="muted">
          The period default leaves laboratory and athletic subjects as saved. A subject or offering
          setting overrides it.
        </p>
      </fieldset>
      {error && (
        <>
          <p role="alert" className="academic-field-error">
            {error}
          </p>
          <Button type="button" variant="secondary" onClick={onReload}>
            Reload saved rules
          </Button>
        </>
      )}
      {saved && <p role="status">Rules saved. They apply to the next generated timetable.</p>}
      <div className="draft-actions">
        <Button type="submit" disabled={busy} loading={busy}>
          Save rules
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={busy}
          onClick={() => {
            setShape(COMMUTER_DEFAULTS);
            setPolicy('flexible');
          }}
        >
          Fill commuter defaults
        </Button>
        <Link to={`/admin/ai-scheduling?period=${encodeURIComponent(snapshot.period.id)}`}>
          Generate a timetable
        </Link>
      </div>
    </form>
  );
}
