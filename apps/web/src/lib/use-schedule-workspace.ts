import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { listCalendarSamples, loadSampleCalendar } from './sample-calendar-api';
import { addDays, manilaToday, type CalendarData } from './calendar-model';
import {
  presentationEnabled,
  presentationOnlyBuild,
  presentationCalendar,
  presentationData,
  presentationVersion,
} from './presentation-sample';
import { schedulingSandboxEnabled } from './scheduling-api';
import { subscribeTimetable, timetableRequest } from './publication-api';
import {
  defaultPeriod,
  readWorkspace,
  rememberWorkspace,
  type WorkspaceContext,
  type WorkspacePeriod,
} from './workspace-context';
import type { UserRole } from '../types/ui';

export function useScheduleWorkspace(role: UserRole, dashboard = false) {
  const [params, setParams] = useSearchParams();
  const [context, setContext] = useState<WorkspaceContext>(() => {
    const saved = readWorkspace(role);
    // Reviewed build configuration selects this source, never an API-error fallback.
    if (presentationOnlyBuild)
      return {
        ...saved,
        mode: 'presentation',
        period: presentationVersion,
        draft: '',
        identity: saved.mode === 'presentation' ? saved.identity : '',
      };
    return {
      ...saved,
      period: params.get('period') ?? saved.period,
      mode:
        presentationEnabled && saved.mode === 'presentation'
          ? 'presentation'
          : !schedulingSandboxEnabled
            ? 'published'
            : params.get('review')
              ? 'review'
              : params.get('mode') === 'published'
                ? 'published'
                : saved.mode,
      draft: params.get('review') ?? saved.draft,
    };
  });
  const [periods, setPeriods] = useState<WorkspacePeriod[]>([]);
  const [drafts, setDrafts] = useState<Array<{ id: string; title: string; period_id?: string }>>(
    [],
  );
  const [data, setData] = useState<CalendarData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [errorStatus, setErrorStatus] = useState(0);
  const [notice, setNotice] = useState('');
  const [connected, setConnected] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const previous = useRef<{
    scope: string;
    sequence: number;
    hash: string;
    version: string | null;
  }>(null);
  const prefix = schedulingSandboxEnabled ? 'sandbox/' : '';
  const date = dashboard ? manilaToday() : context.date;
  const month = date.slice(0, 7);
  const first = month + '-01';
  const last = new Date(
    Date.UTC(Number(month.slice(0, 4)), Number(month.slice(5, 7)) + (dashboard ? 1 : 0), 0),
  )
    .toISOString()
    .slice(0, 10);
  const start = dashboard
    ? first
    : addDays(first, -((new Date(first + 'T00:00:00Z').getUTCDay() + 6) % 7));
  const end = dashboard ? last : addDays(last, (7 - new Date(last + 'T00:00:00Z').getUTCDay()) % 7);
  const { period, identity, mode, draft } = context;
  const query = new URLSearchParams({
    start,
    end,
    role,
    section: role === 'student' ? identity : '',
    teacher: role === 'teacher' ? identity : '',
  }).toString();
  function change(patch: Partial<WorkspaceContext>) {
    if (presentationOnlyBuild)
      patch = { ...patch, mode: 'presentation', period: presentationVersion, draft: '' };
    if (patch.draft)
      patch = {
        ...patch,
        period: drafts.find((d) => d.id === patch.draft)?.period_id ?? context.period,
      };
    setContext((c) => ({ ...c, ...patch }));
    if (
      (['period', 'mode', 'draft', 'identity'] as const).some(
        (key) => patch[key] !== undefined && patch[key] !== context[key],
      )
    )
      setData(null);
    const next = new URLSearchParams(params);
    if (patch.period !== undefined) next.set('period', patch.period);
    if (patch.mode !== undefined) {
      next.set('mode', patch.mode);
      if (patch.mode !== 'review') next.delete('review');
    }
    if (patch.draft) {
      next.set('review', patch.draft);
      next.set('mode', 'review');
    } else if (patch.draft === '') next.delete('review');
    if (patch.period !== undefined || patch.mode !== undefined || patch.draft !== undefined)
      setParams(next, { replace: true });
    setNotice('');
  }
  useEffect(() => {
    rememberWorkspace(role, context);
  }, [context, role]);
  useEffect(() => {
    let ignore = false;
    setLoading(true);
    setError('');
    const load =
      mode === 'presentation' && presentationEnabled
        ? presentationData().then((p) => {
            if (!ignore) {
              setPeriods([
                {
                  id: presentationVersion,
                  title: 'Read-only presentation',
                  calendar: p.calendar.calendar,
                },
              ]);
              setContext((c) => ({ ...c, period: presentationVersion }));
            }
          })
        : mode === 'review' && schedulingSandboxEnabled
          ? listCalendarSamples().then((p) => {
              if (!ignore) {
                setDrafts(p);
                if (draft && !p.some((d) => d.id === draft)) {
                  setError('That saved synthetic timetable is unavailable. Choose another sample.');
                  setErrorStatus(404);
                }
                setContext((c) => {
                  const available = p;
                  const selected = c.draft
                    ? available?.find((d) => d.id === c.draft)
                    : (available?.find((d) => d.period_id === c.period) ?? available?.[0]);
                  return {
                    ...c,
                    draft: selected?.id ?? c.draft,
                    period: selected?.period_id ?? c.period,
                  };
                });
              }
            })
          : timetableRequest<{ periods: WorkspacePeriod[] }>(prefix + 'periods').then((p) => {
              if (!ignore) {
                setPeriods(p.periods);
                setContext((c) => ({ ...c, period: defaultPeriod(p.periods, c.period) }));
              }
            });
    load
      .catch((e) => {
        if (!ignore) {
          setError(e.message);
          setErrorStatus(e.status ?? 0);
        }
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, [mode, prefix, refresh, draft]);
  useEffect(() => {
    if (mode !== 'published' || !period) return;
    return subscribeTimetable(
      `${prefix}events/${encodeURIComponent(period)}?${query}`,
      () => setRefresh((n) => n + 1),
      setConnected,
    );
  }, [mode, period, prefix, query]);
  useEffect(() => {
    if (mode === 'review' ? !draft || !drafts.some((d) => d.id === draft) : !period) return;
    const controller = new AbortController();
    setLoading(true);
    setError('');
    const load =
      mode === 'presentation' && presentationEnabled
        ? presentationCalendar(role, identity, start, end)
        : mode === 'review' && schedulingSandboxEnabled
          ? loadSampleCalendar(draft, query, controller.signal)
          : timetableRequest<CalendarData>(
              `${prefix}calendar/${encodeURIComponent(period)}?${query}`,
              undefined,
              controller.signal,
            );
    load
      .then((value) => {
        if (controller.signal.aborted) return;
        if ((schedulingSandboxEnabled || mode === 'presentation') && role !== 'administrator') {
          const choices = role === 'teacher' ? value.teachers : value.sections;
          if (!choices.some((c) => c.id === identity) && choices.length) {
            const choice =
              role === 'student'
                ? (choices.find((c) => c.id === 'syn-bsit-3-A') ?? choices[0])
                : choices[0];
            setContext((c) => ({ ...c, identity: choice.id }));
          }
        }
        const scope = [mode, period, draft, role, identity, start, end].join(':');
        const sequence = value.sequence ?? 0;
        if (previous.current?.scope === scope && sequence < previous.current.sequence) return;
        const hash = JSON.stringify(value.occurrences.map((o) => ({ ...o, version: undefined })));
        if (
          previous.current?.scope === scope &&
          previous.current.version &&
          value.version !== previous.current.version &&
          hash !== previous.current.hash
        )
          setNotice('Your schedule has been updated.');
        previous.current = { scope, sequence, hash, version: value.version };
        setData(value);
      })
      .catch((e) => {
        if (e.name !== 'AbortError') {
          setError(e.message);
          setErrorStatus(e.status ?? 0);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [draft, drafts, end, identity, mode, period, prefix, query, refresh, role, start]);
  const records =
    data?.occurrences.filter(
      (o) =>
        (!schedulingSandboxEnabled && mode !== 'presentation') ||
        role === 'administrator' ||
        (role === 'teacher' ? o.teacher.id === identity : o.section.id === identity),
    ) ?? [];
  return {
    context,
    change,
    periods,
    drafts,
    data,
    records,
    loading,
    error,
    errorStatus,
    notice,
    connected,
    date,
    retry: () => setRefresh((n) => n + 1),
  };
}
