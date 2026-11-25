import { useEffect, useState, type FormEvent } from 'react';
import { institutionalRequest } from '../lib/institutional-api';
import { Button } from '../components/ui/Button';
import { ClassSyncSkeleton } from '../components/loading/ClassSyncLoading';
import type { UserRole } from '../types/ui';

interface Announcement {
  id: string;
  title: string;
  body: string;
  audience: UserRole[];
  revision: number;
  updated_at: string;
}
const audiences: UserRole[] = ['student', 'teacher', 'administrator'];

export function AnnouncementsPage({ role }: { role: UserRole }) {
  const [rows, setRows] = useState<Announcement[] | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [refresh, reload] = useState(0);
  const [busy, setBusy] = useState(false);
  const [editing, edit] = useState<Announcement | null>(null);
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [audience, setAudience] = useState<UserRole[]>(['student', 'teacher']);
  useEffect(() => {
    const controller = new AbortController();
    setRows(null);
    setError('');
    institutionalRequest<{ announcements: Announcement[] }>('community/announcements', {
      role,
      signal: controller.signal,
    })
      .then((value) => {
        if (!controller.signal.aborted) setRows(value.announcements);
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(failure.message);
      });
    return () => controller.abort();
  }, [role, refresh]);
  function clear() {
    edit(null);
    setTitle('');
    setBody('');
    setAudience(['student', 'teacher']);
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await institutionalRequest<Announcement>(
        'community/announcements' + (editing ? `/${editing.id}` : ''),
        {
          role,
          method: editing ? 'PATCH' : 'POST',
          body: {
            title,
            body,
            audience,
            ...(editing ? { expected_revision: editing.revision } : {}),
          },
        },
      );
      clear();
      setNotice(editing ? 'Announcement updated.' : 'Announcement published.');
      reload((value) => value + 1);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Announcement not confirmed.');
      if ([401, 403].includes((failure as { status?: number }).status ?? 0)) setRows(null);
    } finally {
      setBusy(false);
    }
  }
  async function archive(row: Announcement) {
    if (busy) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await institutionalRequest(
        `community/announcements/${row.id}?expected_revision=${row.revision}`,
        { role, method: 'DELETE' },
      );
      if (editing?.id === row.id) clear();
      setNotice('Announcement archived.');
      reload((value) => value + 1);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Archive not confirmed.');
      if ([401, 403].includes((failure as { status?: number }).status ?? 0)) setRows(null);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="workspace-card" aria-busy={busy}>
      <h1>Announcements</h1>
      <p>Current notices from your university.</p>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      <Button variant="secondary" disabled={busy} onClick={() => reload((value) => value + 1)}>
        Refresh announcements
      </Button>
      {role === 'administrator' && (
        <details open={!!editing}>
          <summary>{editing ? 'Edit announcement' : 'Create announcement'}</summary>
          <form onSubmit={save} className="academic-create-period">
            <label htmlFor="announcement-title">Title</label>
            <input
              id="announcement-title"
              maxLength={120}
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={busy}
            />
            <label htmlFor="announcement-body">Message</label>
            <textarea
              id="announcement-body"
              maxLength={3000}
              required
              rows={4}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              disabled={busy}
            />
            <fieldset disabled={busy}>
              <legend>Who should see this?</legend>
              {audiences.map((item) => (
                <label key={item}>
                  <input
                    type="checkbox"
                    checked={audience.includes(item)}
                    onChange={(e) =>
                      setAudience((current) =>
                        e.target.checked
                          ? [...current, item]
                          : current.filter((value) => value !== item),
                      )
                    }
                  />
                  {item === 'administrator'
                    ? 'Administrators'
                    : item === 'teacher'
                      ? 'Teachers'
                      : 'Students'}
                </label>
              ))}
            </fieldset>
            <Button loading={busy} disabled={busy || !audience.length}>
              {busy ? 'Saving…' : editing ? 'Save announcement' : 'Publish announcement'}
            </Button>
            {editing && (
              <Button type="button" variant="secondary" onClick={clear} disabled={busy}>
                Cancel editing
              </Button>
            )}
          </form>
        </details>
      )}
      {!rows && !error && <ClassSyncSkeleton layout="table" label="Loading announcements" />}
      {rows?.length === 0 && <p>No announcements yet.</p>}
      {rows?.map((row) => (
        <article className="workspace-card" key={row.id}>
          <h2 style={{ overflowWrap: 'anywhere' }}>{row.title}</h2>
          <p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{row.body}</p>
          <small>
            Updated{' '}
            {new Intl.DateTimeFormat('en-PH', {
              dateStyle: 'medium',
              timeStyle: 'short',
              timeZone: 'Asia/Manila',
            }).format(new Date(row.updated_at))}
          </small>
          {role === 'administrator' && (
            <div className="draft-actions">
              <Button
                disabled={busy}
                variant="secondary"
                onClick={() => {
                  edit(row);
                  setTitle(row.title);
                  setBody(row.body);
                  setAudience(row.audience);
                }}
              >
                Edit {row.title}
              </Button>
              <Button disabled={busy} variant="secondary" onClick={() => void archive(row)}>
                Archive {row.title}
              </Button>
            </div>
          )}
        </article>
      ))}
    </section>
  );
}
