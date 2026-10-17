import {
  previewContext,
  previewViewer,
  type SchedulePreviewData,
} from '../../data/schedule-preview';
import {
  formatPreviewDate,
  selectAssignments,
  selectUpdates,
  summarizeDay,
} from '../../lib/schedule-preview';
import { roomById, roomCatalog, roomDetailPath } from '../../lib/room-discovery';
import { NextClassSummary } from '../../components/scheduling/NextClassSummary';
import { ScheduleAgenda } from '../../components/scheduling/ScheduleAgenda';
import { rolePath } from '../../routes/route-config';
import { ScheduleUpdates } from './DashboardSupport';

export function StudentDashboard({
  data,
  reference = previewContext.reference,
}: {
  data: SchedulePreviewData | null;
  reference?: string;
}) {
  const assignments = selectAssignments(data, previewViewer('student'));
  const schedule = summarizeDay(assignments, reference);
  const featuredRoom = schedule.next?.room ?? (schedule.current.length === 1 ? schedule.current[0].room : undefined);
  const room = data && featuredRoom ? roomById(roomCatalog(data), featuredRoom.id) : undefined;
  // The summary already presents the current/next assignments. Keep every other
  // remaining record, including a simultaneous assignment, visible in the agenda.
  const featured = new Set([...schedule.current.map((item) => item.id), schedule.next?.id]);
  const laterToday = schedule.remaining.filter((item) => !featured.has(item.id));
  return (
    <div className="student-dashboard">
      <header className="student-dashboard__heading">
        <h1>Your day</h1>
        <p>
          Sample day · {formatPreviewDate(reference)} · {reference.slice(11, 16)}
        </p>
      </header>
      <div className="dashboard-columns">
        <div className="dashboard-primary">
          <NextClassSummary
            schedule={schedule}
            roomAction={room ? roomDetailPath('student', room.id) : undefined}
            action={{ to: rolePath('student', 'schedule'), label: 'View my schedule' }}
          />
          {laterToday.length > 0 && (
            <ScheduleAgenda
              title="Later today"
              occurrences={laterToday}
              emptyMessage="No other classes today"
            />
          )}
        </div>
        <aside className="dashboard-secondary">
          {data && assignments && (
            <ScheduleUpdates updates={selectUpdates(data, assignments)} role="student" />
          )}
        </aside>
      </div>
    </div>
  );
}
