import { useState } from 'react';
import {
  commitRosterImport,
  previewRosterImport,
  type RosterImportPreview,
} from '../lib/admin-operations-api';
import { downloadCsv, toCsv } from '../lib/csv';
import { Button } from '../components/ui/Button';
import { Modal } from '../components/ui/Modal';
import './admin-operations.css';

const MAX_BYTES = 1_048_576;
const readText = (file: File) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error('The file could not be read.'));
    reader.readAsText(file, 'utf-8');
  });

export function RosterImportDialog({
  periodId,
  onClose,
  onImported,
}: {
  periodId: string;
  onClose: () => void;
  onImported: (count: number) => void;
}) {
  const [csv, setCsv] = useState('');
  const [preview, setPreview] = useState<RosterImportPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError('');
    try {
      await action();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The import could not be completed.');
    } finally {
      setBusy(false);
    }
  }
  function choose(file: File | undefined) {
    setPreview(null);
    setCsv('');
    setError('');
    if (!file) return;
    if (file.size > MAX_BYTES) {
      setError('Choose a CSV file of 1 MB or less.');
      return;
    }
    void run(async () => {
      const content = await readText(file);
      setCsv(content);
      setPreview(await previewRosterImport(periodId, content));
    });
  }
  const commit = () =>
    void run(async () => {
      if (!preview?.rows_hash) return;
      try {
        const result = await commitRosterImport(periodId, {
          csv,
          rows_hash: preview.rows_hash,
          expected_period_revision: preview.period_revision,
        });
        onImported(result.imported);
      } catch (cause) {
        // Whatever changed, the old preview no longer describes what would be imported.
        setPreview(null);
        throw cause;
      }
    });
  const invalid = preview?.rows.filter((row) => row.errors.length) ?? [];
  // Rows that need correction, otherwise every row, so nothing is committed unseen.
  const listed = invalid.length ? invalid : (preview?.rows ?? []);

  return (
    <Modal title="Import students from CSV" onClose={() => { if (!busy) onClose(); }}>
      <div className="modal-body">
        <p>
          Columns: student_id, full_name, email, section and, optionally, enrollment_status. Up to
          2,000 students and 1 MB. Nothing is saved until you confirm, and all rows import together
          or none do. A student from an earlier period is enrolled with their existing record and
          status. Importing does not create sign-in accounts.
        </p>
        <Button
          type="button"
          variant="secondary"
          onClick={() =>
            downloadCsv('roster-template.csv', toCsv(
              ['student_id', 'full_name', 'email', 'section', 'enrollment_status'], [],
            ))
          }
        >
          Download template
        </Button>
        <label>
          CSV file
          <input type="file" accept=".csv,text/csv" disabled={busy} onChange={(event) => choose(event.target.files?.[0])} />
        </label>
        {busy && <p role="status">Working…</p>}
        {error && <p role="alert" className="scheduler-error">{error}</p>}
        {preview && (
          <>
            <p role="status">
              {preview.invalid
                ? `${preview.invalid} of ${preview.total} rows need correction. Fix the file and choose it again.`
                : `${preview.total} rows are ready to import: ${preview.create_new} create new, ${preview.enroll_existing} enroll existing.`}
            </p>
            <div className="table-wrap admin-ops__scroll" tabIndex={0} role="region" aria-label="Import preview">
              <table>
                <thead>
                  <tr><th>Line</th><th>Student ID</th><th>Name</th><th>Section</th><th>Action</th><th>Result</th></tr>
                </thead>
                <tbody>
                  {listed.map((row) => (
                    <tr key={row.line}>
                      <td>{row.line}</td>
                      <td>{row.student_id}</td>
                      <td>{row.full_name}</td>
                      <td>{row.section_label}</td>
                      <td>{row.action === 'enroll_existing' ? 'Enroll existing' : 'Create new'}</td>
                      <td>{row.errors.join(' ') || `Ready · ${row.enrollment_status}${row.note ? ` · ${row.note}` : ''}`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
        <div className="modal-actions">
          <Button type="button" variant="secondary" disabled={busy} onClick={onClose}>Cancel</Button>
          <Button type="button" loading={busy} disabled={busy || !preview?.rows_hash} onClick={commit}>
            Import {preview?.rows_hash ? preview.total : ''} students
          </Button>
        </div>
      </div>
    </Modal>
  );
}
