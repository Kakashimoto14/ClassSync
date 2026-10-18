import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  listSchedulingDrafts,
  loadSchedulingDraft,
  schedulingSandboxEnabled,
  type DraftDetail,
} from '../lib/scheduling-api';
import { IndependentValidation } from './TimetableValidation';
import { SchedulingTimetable } from './SchedulingTimetable';
import { Button } from '../components/ui/Button';
export function ConflictCenterPage() {
  const [drafts, setDrafts] = useState<Array<{ id: string; title: string }>>([]),
    [id, setId] = useState(''),
    [draft, setDraft] = useState<DraftDetail | null>(null),
    [error, setError] = useState(''),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!schedulingSandboxEnabled) return;
    let ignore = false;
    listSchedulingDrafts(0, 'academic')
      .then((v) => {
        if (!ignore) {
          setDrafts(v.drafts);
          setId((old) => old || v.drafts[0]?.id || '');
        }
      })
      .catch((e) => {
        if (!ignore) setError(e.message);
      });
    return () => {
      ignore = true;
    };
  }, [retry]);
  useEffect(() => {
    if (!id || !schedulingSandboxEnabled) return;
    let ignore = false;
    setDraft(null);
    setError('');
    loadSchedulingDraft(id, 'academic')
      .then((v) => {
        if (!ignore) setDraft(v);
      })
      .catch((e) => {
        if (!ignore) setError(e.message);
      });
    return () => {
      ignore = true;
    };
  }, [id, retry]);
  if (!schedulingSandboxEnabled)
    return (
      <p>
        Verified Administrator access is required. Local snapshot validation is disabled in this
        build.
      </p>
    );
  return (
    <div className="weekly-scheduler">
      <p>
        Check a saved timetable against its exact academic snapshot. Publication constraints are
        rechecked separately before publishing.
      </p>
      <label>
        Timetable to validate
        <select value={id} onChange={(e) => setId(e.target.value)}>
          <option value="">Choose a draft</option>
          {drafts.map((d) => (
            <option key={d.id} value={d.id}>
              {d.title}
            </option>
          ))}
        </select>
      </label>
      {error && (
        <div role="alert">
          <p>{error}</p>
          <Button onClick={() => setRetry((n) => n + 1)}>Retry</Button>
        </div>
      )}
      {!drafts.length && !error && (
        <p>
          No academic drafts available. <Link to="/admin/ai-scheduling">Generate a timetable</Link>{' '}
          to begin.
        </p>
      )}
      {draft && (
        <>
          <IndependentValidation
            key={draft.id}
            input={draft.input_snapshot}
            assignments={draft.generation_result.assignments}
          />
          <Link
            className="text-action"
            to={`/admin/schedule-manager/drafts/${draft.id}?source=academic`}
          >
            Review this saved draft
          </Link>
          <SchedulingTimetable
            key={'grid' + draft.id}
            input={draft.input_snapshot}
            result={draft.generation_result}
          />
        </>
      )}
      <details>
        <summary>Planned AI assistance</summary>
        <p>
          Language-model explanations and suggested resolutions are planned. Current checks use the
          independent deterministic validator.
        </p>
      </details>
    </div>
  );
}
