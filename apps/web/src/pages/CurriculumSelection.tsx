import { useEffect, useState } from 'react';
import { ClassSyncSkeleton } from '../components/loading/ClassSyncLoading';
import {
  loadCurriculumCatalog,
  type AcademicRecord,
  type CurriculumCatalog,
} from '../lib/academic-api';
import { Button } from '../components/ui/Button';

export function CurriculumSelection({
  record,
  onChange,
}: {
  record: AcademicRecord;
  onChange: (value: AcademicRecord) => void;
}) {
  const [catalog, setCatalog] = useState<CurriculumCatalog | null>(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [selected, setSelected] = useState(
    record.kind === 'subjects' || record.kind === 'sections'
      ? (record.curriculum_version_id ?? '')
      : '',
  );
  const [institute, setInstitute] = useState('');
  useEffect(() => {
    let ignore = false;
    loadCurriculumCatalog()
      .then((value) => {
        if (!ignore) setCatalog(value);
      })
      .catch((e) => {
        if (!ignore) setError(e.message);
      });
    return () => {
      ignore = true;
    };
  }, [retry]);
  if (record.kind !== 'subjects' && record.kind !== 'sections') return null;
  const source = catalog?.versions.find((v) => v.id === selected);
  return (
    <fieldset className="curriculum-review">
      <legend>Versioned curriculum review</legend>
      <p>
        39 sources · 8 programs. Extracted courses require review. Entry cohort stays assigned when
        year level changes. Puray sources remain separate.
      </p>
      {error && (
        <>
          <p role="alert">{error}</p>
          <Button
            type="button"
            onClick={() => {
              setError('');
              setRetry((n) => n + 1);
            }}
          >
            Retry curriculum catalog
          </Button>
        </>
      )}
      {!catalog && !error && <ClassSyncSkeleton rows={2} label="Loading curriculum sources" />}
      {catalog && (
        <>
          <label>
            Institute filter
            <select value={institute} onChange={(e) => setInstitute(e.target.value)}>
              <option value="">All institutes</option>
              {['ICS', 'IBE', 'ITE'].map((i) => (
                <option key={i}>{i}</option>
              ))}
            </select>
          </label>
          <label>
            Curriculum source
            <select
              value={selected}
              onChange={(e) => {
                setSelected(e.target.value);
                if (record.kind === 'sections') {
                  const v = catalog.versions.find((v) => v.id === e.target.value);
                  onChange({
                    ...record,
                    curriculum_version_id: v?.id ?? null,
                    entry_cohort_year: v ? Number(v.entry_cohort) : null,
                    program_id: v ? catalog.program_ids[v.program] : record.program_id,
                  });
                }
              }}
            >
              <option value="">Select an explicit source</option>
              {catalog.versions
                .filter((v) => !institute || v.institute === institute || v.id === selected)
                .map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.institute} · {v.program} · cohort {v.entry_cohort} · {v.source_pdf}
                  </option>
                ))}
            </select>
          </label>
          {source && (
            <p>
              Printed curriculum: {source.printed_curriculum_ay}. Source:{' '}
              {source.source_archive_member}. SHA-256: {source.source_sha256}. Applicability needs
              Registrar review.
            </p>
          )}
          {record.kind === 'sections' && (
            <p>
              Entry cohort: {record.entry_cohort_year ?? 'Not assigned'}. This selection does not
              confirm that the section exists.
            </p>
          )}
          {record.kind === 'subjects' && (
            <label>
              Exact curriculum course
              <select
                value={record.curriculum_course_id ?? ''}
                onChange={(e) => {
                  const c = catalog.courses.find((c) => c.id === e.target.value);
                  if (c)
                    onChange({
                      ...record,
                      code: c.subject_code,
                      name: c.subject_title,
                      year_level: Number(c.year_level),
                      semester: c.semester === '1' ? 'first' : c.semester === '2' ? 'second' : null,
                      program_ids: [catalog.program_ids[c.program]],
                      curriculum_version_id: c.curriculum_version_id,
                      curriculum_course_id: c.id,
                      provenance: 'source-supplied',
                      required_weekly_minutes: null,
                      patterns: [],
                      curriculum_review_verified: false,
                      contact_minutes_verified: false,
                    });
                }}
              >
                <option value="">Select a source course</option>
                {catalog.courses
                  .filter((c) => c.curriculum_version_id === selected)
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.subject_code} · {c.subject_title} · Year {c.year_level} / semester{' '}
                      {c.semester} · p.{c.pdf_page} · Lec {c.lec_hours_printed} / Lab{' '}
                      {c.lab_hours_printed} / Units {c.units_printed}
                    </option>
                  ))}
              </select>
            </label>
          )}
          <p>
            Printed hours are evidence only. Enter approved weekly minutes and patterns separately.
            Saving an incomplete review record does not make it ready to schedule.
          </p>
        </>
      )}
    </fieldset>
  );
}
