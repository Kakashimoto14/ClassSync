import { useEffect, useState } from 'react';
import { useUniversitySession } from '../auth/university-session-context';
import { institutionalRequest } from './institutional-api';
import type { UserRole } from '../types/ui';

export interface PublishedRoom {
  id: string;
  name: string;
  building: string;
  floor: string | null;
  location: string | null;
  room_type: string | null;
  capacity: number | null;
  equipment: string[];
}

export function usePublishedRoomDirectory(role: UserRole, period: string, version?: string | null) {
  const { state } = useUniversitySession();
  const authority =
    state.status === 'authorized' && state.membership.role === role
      ? `${state.membership.uid}:${role}:${state.membership.membership_revision}`
      : '';
  const scope = authority && period && version ? `${authority}:${period}:${version}` : '';
  const [result, setResult] = useState<{ scope: string; rooms: PublishedRoom[]; error: string }>();
  const [attempt, retry] = useState(0);
  useEffect(() => {
    if (!scope) return;
    const controller = new AbortController();
    setResult(undefined);
    institutionalRequest<{ version: string; rooms: PublishedRoom[] }>(
      `timetables/rooms/${encodeURIComponent(period)}`,
      { role, signal: controller.signal },
    )
      .then((value) => {
        if (!controller.signal.aborted)
          setResult({
            scope,
            rooms: value.version === version ? value.rooms : [],
            error:
              value.version === version
                ? ''
                : 'The timetable changed. Refresh your schedule to load current rooms.',
          });
      })
      .catch((error) => {
        if (!controller.signal.aborted) setResult({ scope, rooms: [], error: error.message });
      });
    return () => controller.abort();
  }, [scope, role, period, version, attempt]);
  const current = scope && result?.scope === scope ? result : undefined;
  return {
    rooms: current?.rooms ?? [],
    error: current?.error ?? '',
    loading: !!scope && !current,
    available: !!scope && !!current && !current.error,
    retry: () => retry((value) => value + 1),
  };
}
