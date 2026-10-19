import { useEffect, useState } from 'react';
import { presentationData } from '../../lib/presentation-sample';
import { Button } from '../ui/Button';

export function PresentationConflictSummary() {
  const [sample, setSample] = useState<Awaited<ReturnType<typeof presentationData>>>();
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let ignore = false;
    setError(false);
    presentationData()
      .then((value) => {
        if (!ignore) setSample(value);
      })
      .catch(() => {
        if (!ignore) setError(true);
      });
    return () => {
      ignore = true;
    };
  }, [attempt]);
  return (
    <section className="workspace-card" aria-label="Frozen sample conflict summary">
      <h2>Sample conflict summary</h2>
      {error ? (
        <div role="alert">
          <p>Couldn't load the bundled sample.</p>
          <Button variant="secondary" onClick={() => setAttempt((n) => n + 1)}>
            Retry sample
          </Button>
        </div>
      ) : !sample ? (
        <p role="status">Loading sample summary…</p>
      ) : (
        <>
          <p className="source-label">{sample.metadata.version} · Synthetic · Frozen export</p>
          <p>
            <strong>{sample.metadata.hard_conflicts_at_export} hard conflicts at export</strong>
          </p>
          <p>
            {sample.metadata.offerings} offerings · {sample.metadata.sessions_per_week} weekly
            sessions
          </p>
          <p>
            This records server validation when the sample was exported. No new validation or live
            conflict analysis has been performed.
          </p>
        </>
      )}
    </section>
  );
}
