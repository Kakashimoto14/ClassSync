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
import { ClassSyncSkeleton } from '../components/loading/ClassSyncLoading';
import { appMode } from '../config/runtime-config';
const connectedWorkspace = appMode === 'institutional' || schedulingSandboxEnabled;
export function ConflictCenterPage() {
  const [loading, setLoading] = useState(true);
  const [drafts, setDrafts] = useState<Array<{ id: string; title: string }>>([]),
    [id, setId] = useState(''),
    [draft, setDraft] = useState<DraftDetail | null>(null),
    [error, setError] = useState(''),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!connectedWorkspace) return;
    let ignore = false;
    setLoading(true);
    listSchedulingDrafts(0, 'academic')
      .then((v) => {
        if (!ignore) {
          setDrafts(v.drafts);
          setId((old) => old || v.drafts[0]?.id || '');
        }
      })
      .catch((e) => {
        if (!ignore) setError(e.message);
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, [retry]);
  useEffect(() => {
    if (!id || !connectedWorkspace) return;
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
  if (!connectedWorkspace)
    return (
      <p>
        Verified Administrator access is required. Local snapshot validation is disabled in this
        build.
      </p>
    );
  return (
    <div className="weekly-scheduler admin-conflicts">
      <header className="admin-conflicts__intro"><p className="eyebrow">Deterministic validation</p><p>Validate a saved timetable against its exact academic snapshot before review or publication.</p><span className="status status--info">Independent validator</span></header>
      <div className="admin-conflicts__toolbar"><label>
        Timetable draft
        <select value={id} onChange={(e) => setId(e.target.value)}>
          <option value="">{drafts.length ? 'Choose a draft' : 'No saved drafts'}</option>
          {drafts.map((d) => (<option key={d.id} value={d.id}>{d.title}</option>))}
        </select>
      </label><Button disabled={!id || loading} onClick={() => setRetry((n) => n + 1)}>Validate selected draft</Button></div>
      <p className="conflict-validation-note">Deterministic independent validation · language-model explanations are not enabled.</p>
      {error && (
        <div role="alert">
          <p>{error}</p>
          <Button onClick={() => setRetry((n) => n + 1)}>Retry</Button>
        </div>
      )}
      {loading && <ClassSyncSkeleton layout="table" label="Loading saved timetables" />}
      {!loading && !drafts.length && !error && (
        <section className="workspace-card conflict-empty-state">
          <p className="academic-setup__eyebrow">Nothing to validate yet</p>
          <h2>Generate a draft first</h2>
          <p>
            The conflict center reviews saved timetable drafts against their original academic
            inputs. It does not create schedules or publish changes.
          </p>
          <ul className="conflict-empty-checklist" aria-label="Checks run during validation">
            {['Room, faculty and section overlaps','Operating windows and availability','Room and instructor eligibility','Weekly and daily workload limits','Required session minutes and patterns'].map((item) => <li key={item}><span aria-hidden="true">✓</span>{item}</li>)}
          </ul>
          <div className="draft-actions">
            <Link className="button" to="/admin/ai-scheduling">
              Open schedule generation
            </Link>
            <Link className="button button--secondary" to="/admin/academic">
              Review academic setup
            </Link>
          </div>
        </section>
      )}
      {draft && (
        <>
          <IndependentValidation
            key={draft.id}
            input={draft.input_snapshot}
            assignments={draft.generation_result.assignments}
          />
          <Link
            className="button button--secondary"
            to={`/admin/schedule-manager/drafts/${draft.id}?source=academic`}
          >
            Review this saved draft
          </Link>
          <details>
            <summary>Browse the saved timetable</summary>{' '}
            <SchedulingTimetable
              key={'grid' + draft.id}
              input={draft.input_snapshot}
              result={draft.generation_result}
            />
          </details>
        </>
      )}
    </div>
  );
}
