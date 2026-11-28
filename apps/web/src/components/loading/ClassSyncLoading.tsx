import { useEffect, useState } from 'react';
import { ClassSyncLogo } from '../brand/ClassSyncLogo';
import './loading.css';

export function ClassSyncPageLoader({
  label = 'Syncing academic workspace…',
  skeleton = false,
}: {
  label?: string;
  skeleton?: boolean;
}) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => setSlow(true), 4000);
    return () => window.clearTimeout(timer);
  }, []);
  return (
    <main className="classsync-page-loader" role="status" aria-live="polite" aria-busy="true">
      <ClassSyncLogo variant="symbol" size="small" decorative />
      <span className="classsync-loading-ring" aria-hidden="true" />
      <strong>{label}</strong>
      {slow && (
        <span>
          {label.startsWith('Waking')
            ? 'This takes a few seconds on first load.'
            : 'Waking ClassSync services — this takes a few seconds on first load.'}
        </span>
      )}
      {skeleton && (
        <span className="classsync-page-loader__bars" aria-hidden="true">
          <span className="classsync-skeleton__item" />
          <span className="classsync-skeleton__item" />
          <span className="classsync-skeleton__item" />
        </span>
      )}
    </main>
  );
}

export function ClassSyncInlineSpinner() {
  return <span className="classsync-inline-spinner" aria-hidden="true" />;
}

type SkeletonLayout = 'rows' | 'kpis' | 'table' | 'timetable';

export function ClassSyncSkeleton({
  layout = 'rows',
  rows = 4,
  label = 'Loading content',
}: {
  layout?: SkeletonLayout;
  rows?: number;
  label?: string;
}) {
  return (
      <div className={`classsync-skeleton classsync-skeleton--${layout}`} role="status" aria-live="polite" aria-busy="true" aria-label={label}>
      <span className="visually-hidden">{label}…</span>
      {Array.from({ length: layout === 'kpis' ? 3 : rows }, (_, index) => (
        <span className="classsync-skeleton__item" key={index} />
      ))}
    </div>
  );
}

/** Page-shaped placeholder inside the shell: header, command bar, then the primary view. */
export function ClassSyncPageSkeleton({ path, label }: { path: string; label: string }) {
  const layout: SkeletonLayout = /\/dashboard$/.test(path)
    ? 'kpis'
    : /\/(schedule|calendar)$/.test(path)
      ? 'timetable'
      : 'table';
  return (
    <div className="page-view classsync-page-skeleton">
      <span className="classsync-page-skeleton__heading classsync-skeleton__item" aria-hidden="true" />
      <span className="classsync-page-skeleton__bar classsync-skeleton__item" aria-hidden="true" />
      <ClassSyncSkeleton layout={layout} rows={layout === 'timetable' ? 12 : 6} label={label} />
    </div>
  );
}
