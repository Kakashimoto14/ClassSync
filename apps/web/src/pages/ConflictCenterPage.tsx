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
import { InlineError } from '../components/ui/InlineError';
import { PageHeader } from '../components/layout/PageHeader';
import { CommandBar, CommandField } from '../components/layout/CommandBar';
import { MetaDetails } from '../components/layout/MetaDetails';
import './scheduling.css';
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
    <div className="weekly-scheduler admin-conflicts scheduling-page">
      <PageHeader
        title="Conflict center"
        meta={<span>Check a saved timetable against its exact academic snapshot.</span>}
        actions={
          <Button disabled={!id || loading} onClick={() => setRetry((n) => n + 1)}>
            Validate selected draft
          </Button>
        }
      />
      <CommandBar label="Draft to validate">
        <CommandField label="Timetable draft" wide>
          <select value={id} onChange={(e) => setId(e.target.value)}>
            <option value="">{drafts.length ? 'Choose a draft' : 'No saved drafts'}</option>
            {drafts.map((d) => (
              <option key={d.id} value={d.id}>
                {d.title}
              </option>
            ))}
          </select>
        </CommandField>
      </CommandBar>
      <MetaDetails summary="How validation works">
        <p>Deterministic independent validation · language-model explanations are not enabled.</p>
      </MetaDetails>
      {error && (
        <InlineError
          title="Couldn't load saved timetables"
          message={error}
          onRetry={() => {
            setError('');
            setRetry((n) => n + 1);
          }}
        />
      )}
      {loading && <ClassSyncSkeleton layout="table" label="Loading saved timetables" />}
      {!loading && !drafts.length && !error && (
        <section className="workspace-card conflict-empty-state">
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
