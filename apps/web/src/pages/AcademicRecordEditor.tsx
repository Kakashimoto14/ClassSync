import { useRef, useState, type FormEvent } from 'react';
import { Button } from '../components/ui/Button';
import type { ActivityType, Assignment, SessionPattern, Window } from '../../../../packages/shared-types/src/scheduling';
import { saveAcademicRecord, type AcademicKind, type AcademicRecord, type AcademicSnapshot } from '../lib/academic-api';
import type { AcademicResource } from '../../../../packages/shared-types/src/scheduling';
import { academicLabel, academicRecords } from '../lib/academic-labels';
import { CurriculumSelection } from './CurriculumSelection';
import { LockedAssignmentsEditor } from './LockedAssignmentsEditor';
import { appMode } from '../config/runtime-config';
import { suppliedAcademicProgramCatalog } from '../data/academic-program-catalog';
import { PatternPolicySelect, ShapeRuleFields } from './SchedulingRuleFields';

const dayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const activityOptions: Array<{ value: ActivityType; label: string }> = [
  { value: 'academic_instruction', label: 'Lecture / general instruction' },
  { value: 'computer_lab_instruction', label: 'Computer laboratory instruction' },
  { value: 'bse_science_instruction', label: 'BSEd Science laboratory instruction' },
  { value: 'pahfit', label: 'PAHFIT' },
  { value: 'sports', label: 'Sports activity' },
  { value: 'assembly', label: 'Assembly' },
  { value: 'rotc', label: 'ROTC' },
  { value: 'special_booking', label: 'Approved special booking' },
];
const roomTypeOptions = [
  ['lecture_classroom', 'Lecture classroom'],
  ['computer_lab', 'Computer laboratory'],
  ['science_lab', 'Science laboratory'],
  ['special_activity', 'Special activity space'],
  ['athletic_space', 'Athletic space'],
] as const;
const clock = (minute: number) => `${String(Math.floor(minute / 60)).padStart(2, '0')}:${String(minute % 60).padStart(2, '0')}`;
const comma = (text: string) => text.split(',').map(v => v.trim()).filter(Boolean);
const timeSlots = Array.from({ length: 48 }, (_, index) => index * 30);
const endTimeSlots = [...timeSlots.slice(1), 1440];
const referencePlaceholders: Record<string, string> = {
  verification_reference: 'e.g., CDM Academic Calendar AY 2026-2027 · Registrar Memo',
  shared_scope_reference: 'e.g., ICS/IBE/ITE Joint Room & Faculty Review – 1st Sem',
};

function CommaField({ label, initial, onChange }: { label: string; initial: string; onChange: (text: string) => void }) {
  const [text, setText] = useState(initial);
  return <label>{label}<input value={text} onChange={e => { setText(e.target.value); onChange(e.target.value); }}/></label>;
}

export function WeeklyWindows({ label, value, onChange }: { label: string; value: Window[]; onChange: (value: Window[]) => void }) {
  const [drafts, setDrafts] = useState<Array<{ start: number | null; end: number | null; days: number[] }>>([]);
  const grouped = Array.from(value.reduce((groups, window) => {
    const key = `${window.start}:${window.end}`;
    const group = groups.get(key) ?? { start: window.start, end: window.end, days: [] as number[] };
    if (!group.days.includes(window.day)) group.days.push(window.day);
    groups.set(key, group);
    return groups;
  }, new Map<string, { start: number; end: number; days: number[] }>()).values());
  const rows = [...grouped.map(window => ({ ...window, saved: true })), ...drafts.map(window => ({ ...window, saved: false }))];
  const updateGroup = (index: number, change: (window: (typeof rows)[number]) => (typeof rows)[number]) => {
    const current = rows[index];
    const next = change(current);
    if (!current.saved) {
      if (next.days.length && next.start !== null && next.end !== null) {
        onChange([...value, ...next.days.map(day => ({ day, start: next.start!, end: next.end! }))]);
        setDrafts(drafts.filter((_, draftIndex) => draftIndex !== index - grouped.length));
      } else {
        setDrafts(drafts.map((draft, draftIndex) => draftIndex === index - grouped.length ? { start: next.start, end: next.end, days: next.days } : draft));
      }
      return;
    }
    const remaining = value.filter(window => window.start !== current.start || window.end !== current.end);
    onChange([...remaining, ...next.days.map(day => ({ day, start: next.start!, end: next.end! }))]);
  };
  return <fieldset className="academic-windows"><legend>{label} <span className="academic-field-indicator" aria-hidden="true">Required for scheduling readiness</span></legend>
    <p className="muted">Enter the verified days and times that apply. Start and end become required when a day is selected.</p>
    {!value.length && !drafts.length && <p className="muted">No windows supplied.</p>}
    {rows.map((w, i) => <div className="academic-window" key={w.saved ? `${w.start}:${w.end}` : `new:${i}`}>
      <fieldset className="academic-day-options"><legend>Days · window {i + 1}</legend>{dayNames.map((day, dayIndex) => <label className={`academic-checkbox${w.days.includes(dayIndex) ? ' is-selected' : ''}`} key={day}><input type="checkbox" aria-label={`${label} ${day} ${i + 1}`} checked={w.days.includes(dayIndex)} onChange={e => updateGroup(i, current => ({ ...current, days: e.target.checked ? [...current.days, dayIndex] : current.days.filter(selected => selected !== dayIndex) }))}/>{day.slice(0, 3)}</label>)}</fieldset>
      <label>Start <span className="academic-field-indicator" aria-hidden="true">{w.days.length ? 'Required' : 'Optional'}</span><select aria-label={`${label} start ${i + 1}`} required={w.days.length > 0} value={w.start ?? ''} onChange={e => updateGroup(i, current => ({ ...current, start: e.target.value ? Number(e.target.value) : null }))}><option value="">Choose start time</option>{timeSlots.map(slot => <option key={slot} value={slot}>{clock(slot)}</option>)}</select></label>
      <label>End <span className="academic-field-indicator" aria-hidden="true">{w.days.length ? 'Required' : 'Optional'}</span><select aria-label={`${label} end ${i + 1}`} required={w.days.length > 0} disabled={w.end === 1440} value={w.end ?? ''} onChange={e => updateGroup(i, current => ({ ...current, end: e.target.value ? Number(e.target.value) : null }))}><option value="">Choose end time</option>{endTimeSlots.map(slot => <option key={slot} value={slot}>{slot === 1440 ? '24:00 · midnight' : clock(slot)}</option>)}</select></label>
      <Button type="button" variant="ghost" aria-label={`Remove ${label.toLowerCase()} window ${i + 1}`} onClick={() => w.saved ? onChange(value.filter(window => window.start !== w.start || window.end !== w.end)) : setDrafts(drafts.filter((_, draftIndex) => draftIndex !== i - grouped.length))}>Remove</Button>
      <label className="academic-checkbox"><input type="checkbox" aria-label={`${label} ends at midnight ${i + 1}`} checked={w.end === 1440} onChange={e => updateGroup(i, current => ({ ...current, end: e.target.checked ? 1440 : 720 }))}/>Ends at midnight</label>
      {w.start !== null && w.end !== null && w.end <= w.start && <p className="academic-field-error">End must be later than start.</p>}
    </div>)}
    <Button type="button" variant="secondary" onClick={() => setDrafts([...drafts, { days: [], start: null, end: null }])}>Add {label.toLowerCase()} window</Button>
    <p className="muted">Select every applicable day and confirm actual approved times. Menus use 30-minute intervals; they do not assert institutional availability.</p>
  </fieldset>;
}

function ChoiceList({ label, options, value, onChange }: { label: string; options: Array<{ id: string; label: string }>; value: string[]; onChange: (value: string[]) => void }) {
  const [query, setQuery] = useState('');
  return <details className="academic-choices"><summary>{label} · {value.length} selected</summary>
    <label>Search {label.toLowerCase()}<input type="search" value={query} onChange={e => setQuery(e.target.value)}/></label>
    {!options.length && <p>No records available. Save the related records first.</p>}
    <fieldset className="academic-choice-options"><legend>{label}</legend>{options.filter(o => o.label.toLowerCase().includes(query.toLowerCase())).map(o => <label className="academic-checkbox" key={o.id}><input type="checkbox" checked={value.includes(o.id)} onChange={e => onChange(e.target.checked ? [...value, o.id] : value.filter(id => id !== o.id))}/>{o.label}</label>)}</fieldset>
  </details>;
}

function Patterns({ weekly, value, onChange }: { weekly: number | null; value: SessionPattern[]; onChange: (patterns: SessionPattern[]) => void }) {
  const [custom, setCustom] = useState('');
  const [error, setError] = useState('');
  function toggle(id: string, durations: number[], checked: boolean) {
    const existing = value.filter(p => JSON.stringify(p.durations) !== JSON.stringify(durations));
    onChange(checked ? [...existing, { id, durations, distinct_days: true }] : existing);
  }
  return <fieldset className="academic-patterns"><legend>Allowed meeting patterns</legend>
    {weekly === 180 && <>
      <label className="academic-checkbox"><input type="checkbox" checked={value.some(p => JSON.stringify(p.durations) === '[180]')} onChange={e => toggle('one-180', [180], e.target.checked)}/>One 180-minute meeting</label>
      <label className="academic-checkbox"><input type="checkbox" checked={value.some(p => JSON.stringify(p.durations) === '[90,90]')} onChange={e => toggle('two-90', [90, 90], e.target.checked)}/>Two 90-minute meetings on distinct days</label>
    </>}
    {weekly !== 180 && <p>Enter explicit session durations totalling {weekly ?? 'the required'} weekly minutes.</p>}
    <details><summary>Nonstandard contact-hour patterns</summary><label>Session durations in minutes<input value={custom} placeholder="120, 120" onChange={e => setCustom(e.target.value)}/></label>
      <Button type="button" variant="secondary" onClick={() => { const durations = comma(custom).map(Number); if (durations.length && durations.every(n => n > 0 && n <= 1440 && n % 30 === 0) && durations.reduce((a,b)=>a+b,0) === weekly) { onChange([...value, { id: crypto.randomUUID(), durations, distinct_days: true }]); setCustom(''); setError(''); } else { setError('Use positive 30-minute durations that total the required weekly contact minutes.'); } }}>Add meeting pattern</Button>
      {error && <p role="alert" className="academic-field-error">{error}</p>}
      <p className="muted">Sessions use distinct days. Every allowed pattern must equal the required weekly minutes.</p>
    </details>
    <ul>{value.map((p, i) => <li key={`${p.id}:${i}`}>{p.durations.join(' + ')} min {p.distinct_days !== false && p.durations.length > 1 ? '· distinct days' : ''}<Button type="button" variant="ghost" onClick={() => onChange(value.filter((_, n) => n !== i))} aria-label={`Remove pattern ${p.durations.join(' plus ')}`}>Remove</Button></li>)}</ul>
    {(!value.length || (weekly !== null && value.some(p => p.durations.reduce((a, b) => a + b, 0) !== weekly))) && <p className="academic-field-error">Choose at least one pattern; each must total the required weekly minutes.</p>}
  </fieldset>;
}

function initialRecord(kind: AcademicKind, period: string): AcademicRecord {
  const id = crypto.randomUUID();
  const base = { id, kind, active: true };
  if (kind === 'programs') return { ...base, kind, acronym: '', name: '', institute: '', section_policy: 'degree' };
  if (kind === 'subjects') return { ...base, kind, code: '', name: '', program_ids: [], required_weekly_minutes: 180, patterns: [{ id: 'one-180', durations: [180], distinct_days: true }, { id: 'two-90', durations: [90, 90], distinct_days: true }] };
  if (kind === 'sections') return { ...base, kind, period_id: period, program_id: '', year_level: null, section_letter: null };
  if (kind === 'faculty') return { ...base, kind, name: '', subject_ids: [], availability: [] };
  if (kind === 'resources') return { ...base, kind, name: '', building: '', source: 'administrator-supplied', schedulable: false, condition: 'unknown', availability: [], verification_note: '' };
  if (kind === 'offerings') return { ...base, kind, subject_id: '', section_id: '', activity_type: 'academic_instruction', teacher_ids: [], room_ids: [] };
  return { id: 'rules', kind, operating_windows: [], options: { time_limit_seconds: 15, seed: 42 } };
}

export function AcademicRecordEditor({ kind, snapshot, existing, onSaved, onCancel, onReload }: {
  kind: AcademicKind; snapshot: AcademicSnapshot; existing?: AcademicSnapshot['records'][number]; onSaved: (snapshot: AcademicSnapshot) => void; onCancel: () => void; onReload?: () => void;
}) {
  const [record, setRecord] = useState<AcademicRecord>(() => existing ? structuredClone(existing.record) as AcademicRecord : initialRecord(kind, snapshot.period.id));
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [locks, setLocks] = useState<Assignment[]>(() => record.kind === 'constraints' ? structuredClone(record.locked_assignments ?? []) : []);
  const [enrollments, setEnrollments] = useState(() => JSON.stringify(record.kind === 'constraints' ? record.enrollments ?? [] : [], null, 2));
  const active = useRef(false);
  const update = (name: string, value: unknown) => setRecord(r => {
    const next = { ...r, [name]: value } as AcademicRecord;
      if (r.kind === 'subjects' && next.kind === 'subjects') {
      if (['code', 'name', 'curriculum_version_id', 'curriculum_course_id'].includes(name)) next.curriculum_review_verified = false;
      if (['required_weekly_minutes', 'patterns', 'pattern_policy', 'lec_hours', 'lab_hours'].includes(name)) next.contact_minutes_verified = false;
    } else if (r.kind === 'sections' && next.kind === 'sections') {
      if (['entry_cohort_year', 'curriculum_version_id'].includes(name)) next.cohort_assignment_verified = false;
      if (['year_level', 'section_letter', 'custom_label', 'program_id'].includes(name)) next.identity_verified = false;
      if (name === 'population') next.population_verified = false;
    } else if (r.kind === 'faculty' && next.kind === 'faculty') {
      if (name === 'subject_ids') next.eligibility_verified = false;
      if (['availability', 'unavailable'].includes(name)) next.availability_verified = false;
      if (['max_weekly_minutes', 'max_daily_minutes', 'weekly_unit_cap'].includes(name)) next.workload_verified = false;
    } else if (r.kind === 'resources' && next.kind === 'resources') {
      if (['availability', 'blocked'].includes(name)) next.availability_verified = false;
      if (name === 'room_type') next.type_verified = false;
      if (name === 'capacity') next.capacity_verified = false;
      if (name === 'equipment') next.equipment_verified = false;
    } else if (r.kind === 'offerings' && next.kind === 'offerings') {
      if (['subject_id', 'section_id', 'teacher_ids', 'room_ids', 'activity_type'].includes(name)) next.term_offering_verified = false;
      if (['weekly_minutes_override', 'patterns_override', 'pattern_policy'].includes(name)) next.override_requirements_verified = false;
    } else if (r.kind === 'constraints' && next.kind === 'constraints' && name === 'operating_windows') {
      next.operating_windows_verified = false;
    } else if (r.kind === 'constraints' && next.kind === 'constraints' && name === 'verification_reference') {
      next.operating_windows_verified = false;
    } else if (r.kind === 'constraints' && next.kind === 'constraints' && name === 'shared_scope_reference') {
      next.shared_scope_verified = false;
    }
    return next;
  });
  const changeLocks = (value: Assignment[]) => {
    setLocks(value);
    update('all_intended_offerings_supplied', false);
    update('shared_scope_verified', false);
  };
  const choices = (k: AcademicKind) => {
    const rows = academicRecords(snapshot, k);
    if (k === 'resources' && record.kind === 'offerings') {
      const subject = academicRecords(snapshot, 'subjects').find(r => r.id === record.subject_id);
      const section = academicRecords(snapshot, 'sections').find(r => r.id === record.section_id);
      const requiredType = record.required_room_type || (subject?.kind === 'subjects' ? subject.required_room_type : null);
      const resources = rows.filter(r => r.kind === 'resources') as Array<AcademicResource & { id: string; kind: 'resources' }>;
      return resources.filter(r => {
        if (!r.active || !r.schedulable) return false;
        if (r.allowed_activity_types && !r.allowed_activity_types.includes(record.activity_type ?? 'academic_instruction')) return false;
        if (r.allowed_program_ids && (section?.kind !== 'sections' || !r.allowed_program_ids.includes(section.program_id))) return false;
        if (requiredType && (r.room_type !== requiredType || !r.type_verified)) return false;
        return true;
      }).map(r => ({
        id: r.id,
        label: `${academicLabel(r, snapshot)}${r.condition !== 'operational' || !r.type_verified ? ' · verification required' : ''}`,
      }));
    }
    return rows.map(r => ({ id: r.id, label: academicLabel(r, snapshot) }));
  };
  const text = (label: string, name: string, value: string | null | undefined, required = false, disabled = false) => <label>{label} <span className="academic-field-indicator" aria-hidden="true">{required ? 'Required' : 'Optional'}</span><input name={name} required={required} disabled={disabled} value={value ?? ''} placeholder={referencePlaceholders[name] ?? (required ? `Enter ${label.toLowerCase()}` : 'Optional')} onChange={e => update(name, e.target.value || (required ? '' : null))}/></label>;
  const number = (label: string, name: string, value: number | null | undefined, step = 1, min = 0) => <label>{label} <span className="academic-field-indicator" aria-hidden="true">Optional</span><input name={name} type="number" min={min} step={step} value={value ?? ''} placeholder="Optional" onChange={e => update(name, e.target.value === '' ? null : Number(e.target.value))}/></label>;
  const check = (label: string, name: string, value: boolean | undefined) => <label className="academic-checkbox"><input type="checkbox" checked={value ?? false} onChange={e => update(name, e.target.checked)}/>{label} <span className="academic-field-indicator" aria-hidden="true">Optional</span></label>;
  async function submit(event: FormEvent) {
    event.preventDefault(); if (active.current) return;
    active.current = true; setBusy(true); setError('');
    try {
      const next = record.kind === 'constraints' ? { ...record, locked_assignments: locks, enrollments: appMode === 'institutional' ? record.enrollments ?? [] : JSON.parse(enrollments) } : record;
      if (next.kind === 'subjects' && next.required_weekly_minutes == null && !next.curriculum_version_id) throw new Error('Enter required weekly contact minutes.');
      if (next.kind === 'subjects' && next.required_weekly_minutes != null && (!next.patterns?.length || next.patterns.some(p => p.durations.reduce((a, b) => a + b, 0) !== next.required_weekly_minutes))) throw new Error('Allowed meeting patterns must total the required weekly contact minutes.');
      onSaved(await saveAcademicRecord(snapshot.period.id, { expected_revision: existing?.revision ?? 0, record: next }));
    } catch (e) { setError(e instanceof Error ? e.message : 'Record save failed.'); }
    finally { active.current = false; setBusy(false); }
  }
  const program = record.kind === 'sections' ? academicRecords(snapshot, 'programs').find(p => p.id === record.program_id) : undefined;
  const catalogProgram = record.kind === 'programs' ? suppliedAcademicProgramCatalog.find(item => item.id === record.id) : undefined;
  const savedPrograms = academicRecords(snapshot, 'programs');
  const customSection = program?.kind === 'programs' && program.section_policy === 'custom';
  const cdm = record.kind === 'resources' && record.id.startsWith('cdm-');
  return <form className="workspace-card academic-record-form" onSubmit={submit} aria-label={`${existing ? 'Edit' : 'New'} ${kind} record`} aria-busy={busy}>
    <h2>{existing ? 'Edit' : 'New'} {kind === 'faculty' ? 'faculty member' : kind === 'constraints' ? 'scheduling constraints' : kind === 'offerings' ? 'subject offering' : kind.replace(/s$/, '')}</h2>
    <fieldset disabled={busy} className="academic-form-fields">
      {record.kind === 'programs' && <>
        {existing && !catalogProgram ? <>
          <p className="muted">This saved program is not in the current supplied catalog. Its existing identity is preserved; review the source before changing it.</p>
          <div className="academic-field-grid">{text('Program acronym', 'acronym', record.acronym, true)}{text('Program name', 'name', record.name, true)}{text('Institute', 'institute', record.institute, true)}</div>
          <label>Section naming policy<select value={record.section_policy ?? 'degree'} onChange={e => update('section_policy', e.target.value)}><option value="degree">Structured year and section letter</option><option value="custom">Program-specific label</option></select></label>
        </> : existing ? <>
          <p className="muted">This program started from the supplied catalog. Edit its details for this academic period; the stable record ID remains unchanged.</p>
          <div className="academic-field-grid">{text('Program acronym', 'acronym', record.acronym, true)}{text('Program name', 'name', record.name, true)}{text('Institute', 'institute', record.institute, true)}</div>
          <label>Section naming policy<select value={record.section_policy ?? 'degree'} onChange={e => update('section_policy', e.target.value)}><option value="degree">Structured year and section letter</option><option value="custom">Program-specific label</option></select></label>
        </> : <>
          <label>Program suggestion <span className="academic-field-indicator" aria-hidden="true">Optional</span><select value={catalogProgram?.id ?? ''} onChange={e => { if (e.target.value === '__custom__') { setRecord({ id: crypto.randomUUID(), kind: 'programs', acronym: '', name: '', institute: '', section_policy: 'degree', active: true }); return; } const selected = suppliedAcademicProgramCatalog.find(item => item.id === e.target.value); if (selected) setRecord({ ...selected, kind: 'programs', active: true }); }}><option value="">Choose a supplied suggestion</option>{suppliedAcademicProgramCatalog.filter(item => !savedPrograms.some(saved => saved.id === item.id)).map(item => <option key={item.id} value={item.id}>{item.acronym} · {item.name}</option>)}<option value="__custom__">Create another program</option></select></label>
          {catalogProgram ? <>
            <p className="muted">The supplied catalog is editable starting data and is not Registrar-verified.</p>
            <div className="academic-field-grid">{text('Program acronym', 'acronym', record.acronym, true)}{text('Program name', 'name', record.name, true)}{text('Institute', 'institute', record.institute, true)}</div>
            <label>Section naming policy<select value={record.section_policy ?? 'degree'} onChange={e => update('section_policy', e.target.value)}><option value="degree">Structured year and section letter</option><option value="custom">Program-specific label</option></select></label>
          </> : <>
            <div className="academic-field-grid">{text('Program acronym', 'acronym', record.acronym, true)}{text('Program name', 'name', record.name, true)}{text('Institute', 'institute', record.institute, true)}</div>
            <label>Section naming policy<select value={record.section_policy ?? 'degree'} onChange={e => update('section_policy', e.target.value)}><option value="degree">Structured year and section letter</option><option value="custom">Program-specific label</option></select></label>
          </>}
        </>}
      </>}
      {record.kind === 'subjects' && <>
        <CurriculumSelection record={record} onChange={setRecord}/>
        {check('Curriculum source or code equivalency reviewed with Registrar', 'curriculum_review_verified', record.curriculum_review_verified)}
        {text('Registrar/source review reference', 'curriculum_review_reference', record.curriculum_review_reference, record.curriculum_review_verified)}
        {check('Contact minutes and delivery patterns approved', 'contact_minutes_verified', record.contact_minutes_verified)}
        {text('Approved minutes/pattern reference', 'contact_minutes_reference', record.contact_minutes_reference, record.contact_minutes_verified)}
        {!record.curriculum_version_id && <p className="muted">A subject without an exact versioned source requires an approved Registrar exception or equivalency before institutional readiness can pass.</p>}
        <div className="academic-field-grid">{text('Subject code', 'code', record.code, true)}{text('Subject name', 'name', record.name, true)}{number('Lecture hours per week', 'lec_hours', record.lec_hours, 1)}{number('Lab hours per week', 'lab_hours', record.lab_hours, 1)}{number('Credit units', 'units', record.units, 1)}{number('Required weekly contact minutes', 'required_weekly_minutes', record.required_weekly_minutes, 30, 30)}</div>
        <p className="muted">{record.curriculum_version_id ? 'No contact-minute default is applied to prospectus courses. Enter the approved minutes and meeting patterns.' : '180 minutes is a proposed default. Contact minutes are not academic credit units.'}</p>
        <ChoiceList label="Associated programs" options={choices('programs')} value={record.program_ids ?? []} onChange={v => update('program_ids', v)}/>
        <Patterns weekly={record.required_weekly_minutes ?? null} value={record.patterns ?? []} onChange={v => update('patterns', v)}/>
        {record.required_weekly_minutes === 180 && <PatternPolicySelect label="180-minute pattern policy" emptyLabel="Follow the period default" value={record.pattern_policy} onChange={v => update('pattern_policy', v)}/>}
        <details><summary>Classroom requirements</summary><label>Required room type<select value={record.required_room_type ?? ''} onChange={e => update('required_room_type', e.target.value || null)}><option value="">No specific type</option>{roomTypeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><CommaField label="Required equipment (comma-separated)" initial={record.required_equipment?.join(', ') ?? ''} onChange={value => update('required_equipment', comma(value))}/>{number('Minimum classroom capacity', 'minimum_capacity', record.minimum_capacity, 1, 1)}</details>
      </>}
      {record.kind === 'sections' && <>
        <CurriculumSelection record={record} onChange={setRecord}/>
        <label>Program<select required value={record.program_id} onChange={e => { update('program_id', e.target.value); update('custom_label', null); }}><option value="">Choose program</option>{choices('programs').map(p => <option key={p.id} value={p.id}>{p.label}</option>)}</select></label>
        {customSection ? text('Program-specific section label', 'custom_label', record.custom_label, true) : <div className="academic-field-grid"><label>Year level<select required value={record.year_level ?? ''} onChange={e => update('year_level', e.target.value ? Number(e.target.value) : null)}><option value="">Choose year level</option>{[1, 2, 3, 4].map(year => <option key={year} value={year}>{year}</option>)}</select></label><label>Section identifier<select required value={record.section_letter ?? ''} onChange={e => update('section_letter', e.target.value || null)}><option value="">Choose section</option>{'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('').map(letter => <option key={letter} value={letter}>{letter}</option>)}</select></label></div>}
        <p className="muted">Belongs to {snapshot.period.title}. Section identifiers are separate from stable database IDs.</p>
        <details><summary>Section capacity and student population</summary>{number('Section capacity', 'capacity', record.capacity, 1, 1)}{number('Student population', 'population', record.population, 1, 1)}{check('Population is verified', 'population_verified', record.population_verified)}</details>
        <details><summary>Institutional section verification</summary>{number('Entry cohort year', 'entry_cohort_year', record.entry_cohort_year, 1, 1900)}{check('Cohort-to-curriculum assignment is verified', 'cohort_assignment_verified', record.cohort_assignment_verified)}{check('Official section identity is verified', 'identity_verified', record.identity_verified)}{text('Verification source/reference', 'verification_reference', record.verification_reference, record.cohort_assignment_verified || record.identity_verified || record.population_verified)}</details>
      </>}
      {record.kind === 'faculty' && <>
        {record.synthetic && <p role="status">Synthetic candidate · cannot satisfy institutional scheduling or publication.</p>}
        <div className="academic-field-grid">{text('Faculty name', 'name', record.name, true)}{text('Institutional faculty identifier (optional)', 'institutional_id', record.institutional_id)}</div>
        <ChoiceList label="Eligible teaching subjects" options={choices('subjects')} value={record.subject_ids ?? []} onChange={v => update('subject_ids', v)}/>
        <WeeklyWindows label="Faculty availability" value={record.availability ?? []} onChange={v => update('availability', v)}/>
        <details><summary>Workload and unavailable times</summary><div className="academic-field-grid">{number('Weekly unit cap', 'weekly_unit_cap', record.weekly_unit_cap, 1, 1)}{number('Maximum weekly teaching minutes', 'max_weekly_minutes', record.max_weekly_minutes, 30)}{number('Maximum daily teaching minutes', 'max_daily_minutes', record.max_daily_minutes, 30)}</div><WeeklyWindows label="Faculty unavailable" value={record.unavailable ?? []} onChange={v => update('unavailable', v)}/></details>
        {check('Subject eligibility is verified', 'eligibility_verified', record.eligibility_verified)}{check('Availability is verified', 'availability_verified', record.availability_verified)}{check('Workload is verified', 'workload_verified', record.workload_verified)}{text('Verification source/reference', 'verification_reference', record.verification_reference, record.eligibility_verified || record.availability_verified || record.workload_verified)}
        {existing && <p>Referenced by {academicRecords(snapshot, 'offerings').filter(o => o.kind === 'offerings' && o.teacher_ids?.includes(record.id)).length} offerings in this period. Manage assignments in Subject Offerings.</p>}
      </>}
      {record.kind === 'resources' && <>
        {cdm && <p className="scheduling-boundary">CdM provisional identity and location are preserved. Metadata assertions apply to this academic period and do not change existing drafts or the source inventory.</p>}
        <div className="academic-field-grid">{text('Resource name', 'name', record.name, true, cdm)}{text('Building or area', 'building', record.building, true, cdm)}{text('Floor (if supplied)', 'floor', record.floor, false, cdm)}</div>
        {record.alias && <p>{record.alias}{record.alias_unconfirmed ? ' · unconfirmed label' : ''}</p>}
        <label>Known operational condition<select value={record.condition ?? 'unknown'} onChange={e => update('condition', e.target.value)}><option value="unknown">Unknown / unverified</option><option value="operational">Confirmed operational</option><option value="maintenance">Maintenance / unavailable</option></select></label>
        {check('Explicitly eligible for scheduling', 'schedulable', record.schedulable)}
        <div className="academic-field-grid"><label>Room type<select value={record.room_type ?? ''} onChange={e => update('room_type', e.target.value || null)}><option value="">Unspecified</option>{roomTypeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>{number('Capacity (if supplied)', 'capacity', record.capacity, 1, 1)}</div>
        {cdm && <p className="muted">The inventory designation is a classification only. Facilities must verify the room type, operation, equipment, capacity and availability separately.</p>}
        {check('Room type is verified', 'type_verified', record.type_verified)}{check('Capacity is verified', 'capacity_verified', record.capacity_verified)}
        <CommaField label="Equipment (comma-separated)" initial={record.equipment?.join(', ') ?? ''} onChange={value => update('equipment', comma(value))}/>{check('Equipment list is verified', 'equipment_verified', record.equipment_verified)}
        <label>Verification source / note<textarea rows={3} value={record.verification_note ?? ''} onChange={e => update('verification_note', e.target.value)}/></label>
        <WeeklyWindows label="Resource availability" value={record.availability ?? []} onChange={v => update('availability', v)}/>
        {check('Availability and blocked windows are verified', 'availability_verified', record.availability_verified)}
        <details><summary>Resource restrictions</summary><WeeklyWindows label="Resource blocked" value={record.blocked ?? []} onChange={v => update('blocked', v)}/><label className="academic-checkbox"><input type="checkbox" checked={record.allowed_program_ids != null} onChange={e => update('allowed_program_ids', e.target.checked ? [] : null)}/>Restrict to selected programs</label>{record.allowed_program_ids != null && <ChoiceList label="Allowed programs" options={choices('programs')} value={record.allowed_program_ids} onChange={v => update('allowed_program_ids', v)}/>}</details>
      </>}
      {record.kind === 'offerings' && <>
        <label>Subject<select required value={record.subject_id} onChange={e => update('subject_id', e.target.value)}><option value="">Choose subject</option>{choices('subjects').map(s => <option key={s.id} value={s.id}>{s.label}</option>)}</select></label>
        <label>Section<select required value={record.section_id} onChange={e => update('section_id', e.target.value)}><option value="">Choose section</option>{choices('sections').map(s => <option key={s.id} value={s.id}>{s.label}</option>)}</select></label>
        <label>Activity type<select value={record.activity_type ?? 'academic_instruction'} onChange={e => { update('activity_type', e.target.value as ActivityType); update('room_ids', []); }}><option value="">Choose activity type</option>{activityOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>
        <ChoiceList label="Assigned or eligible faculty" options={choices('faculty')} value={record.teacher_ids ?? []} onChange={v => update('teacher_ids', v)}/>
        <ChoiceList label="Activity-compatible schedulable rooms" options={choices('resources')} value={record.room_ids ?? []} onChange={v => update('room_ids', v)}/>
        <p className="muted">The inventory marks room purpose only. Verification-required rooms cannot pass scheduling readiness; selected rooms do not imply availability.</p>
        <p className="muted">One selected faculty member is assigned for all sessions. Empty selections are incomplete and block readiness. Subject contact-hour patterns apply unless explicitly overridden.</p>
        <p className="muted">Create an offering only when that subject is confirmed for this term and section. A prospectus requirement does not create a current offering.</p>
        {check('This is an actual approved offering for this period/section', 'term_offering_verified', record.term_offering_verified)}{text('Term offering source/reference', 'verification_reference', record.verification_reference, record.term_offering_verified || record.override_requirements_verified)}
        <details><summary>Offering-specific requirements</summary>{number('Weekly contact-minute override', 'weekly_minutes_override', record.weekly_minutes_override, 30, 30)}
          <label className="academic-checkbox"><input type="checkbox" checked={record.patterns_override != null} onChange={e => { const subject = academicRecords(snapshot, 'subjects').find(s => s.id === record.subject_id); update('patterns_override', e.target.checked && subject?.kind === 'subjects' ? structuredClone(subject.patterns ?? []) : null); update('override_requirements_verified', false); }}/>Override allowed meeting patterns</label>
          {record.patterns_override != null && <Patterns weekly={record.weekly_minutes_override ?? (academicRecords(snapshot, 'subjects').find(s => s.id === record.subject_id) as { required_weekly_minutes?: number } | undefined)?.required_weekly_minutes ?? null} value={record.patterns_override} onChange={v => update('patterns_override', v)}/>}
          <PatternPolicySelect label="180-minute pattern policy override" emptyLabel="Follow the subject or period" value={record.pattern_policy} onChange={v => update('pattern_policy', v)}/>
          {(record.weekly_minutes_override != null || record.patterns_override != null || record.pattern_policy != null) && check('Offering-specific minutes and patterns approved', 'override_requirements_verified', record.override_requirements_verified)}
          <label>Required room-type override<select value={record.required_room_type ?? ''} onChange={e => update('required_room_type', e.target.value || null)}><option value="">No override</option>{roomTypeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>{number('Minimum capacity override', 'minimum_capacity', record.minimum_capacity, 1, 1)}
          <CommaField label="Additional required equipment" initial={record.required_equipment?.join(', ') ?? ''} onChange={value => update('required_equipment', comma(value))}/><CommaField label="Allowed buildings (optional, comma-separated)" initial={record.allowed_buildings?.join(', ') ?? ''} onChange={value => update('allowed_buildings', value.trim() ? comma(value) : null)}/>
        </details>
      </>}
      {record.kind === 'constraints' && <>
        <Button type="button" variant="secondary" onClick={() => setRecord(current => current.kind === 'constraints' ? {
          ...current,
          operating_windows: [0, 1, 2, 3, 4, 5].map(day => ({ day, start: 420, end: 1260 })),
          transition_buffer_minutes: 10,
          verification_reference: 'CDM Academic Calendar AY 2026-2027 · Registrar Memo',
          shared_scope_reference: 'ICS/IBE/ITE Joint Room & Faculty Review – 1st Sem',
          operating_windows_verified: false,
          shared_scope_verified: false,
        } : current)}>Apply Standard Campus Defaults</Button>
        <p className="muted">Fills editable suggestions only. Confirm the calendar, teaching hours, transition time, and review references before checking verification and saving.</p>
        <WeeklyWindows label="Operating hours" value={record.operating_windows ?? []} onChange={v => update('operating_windows', v)}/>
        {check('Operating windows are approved for this academic period', 'operating_windows_verified', record.operating_windows_verified)}{text('Calendar/rules source/reference', 'verification_reference', record.verification_reference, record.operating_windows_verified)}
        <label>Transition buffer <span className="academic-field-indicator" aria-hidden="true">Required</span><select aria-label="Transition buffer" value={record.transition_buffer_minutes ?? 0} onChange={e => update('transition_buffer_minutes', Number(e.target.value))}>{[0, 10, 30, 60, 90, 120].map(n => <option key={n} value={n}>{n} minutes</option>)}</select><small className="muted">Time reserved between consecutive room or faculty assignments.</small></label>
        <ShapeRuleFields value={record.daily_shape} onChange={v => update('daily_shape', v)}/>
        <PatternPolicySelect label="Default pattern for 180-minute subjects" emptyLabel="Use each subject's saved patterns" value={record.pattern_policy_180} onChange={v => update('pattern_policy_180', v)}/>
        {check('I have supplied all intended offerings for this period', 'all_intended_offerings_supplied', record.all_intended_offerings_supplied)}
        <p className="muted">This is an administrator scope declaration, not independent verification of school-wide coverage.</p>
        <p className="muted">Include shared ICS, IBE and ITE rooms/faculty/locked sessions in this same period. Separate periods are not checked against each other.</p>
        {check('Shared ICS/IBE/ITE offerings, faculty, rooms and fixed commitments were reviewed in this period', 'shared_scope_verified', record.shared_scope_verified)}{text('Shared-scope review source/reference', 'shared_scope_reference', record.shared_scope_reference, record.shared_scope_verified)}
        <details><summary>Solver, fixed assignments and enrollment conflicts</summary>
          <label>Solver time limit (seconds)<input type="number" min={1} max={30} step={1} value={record.options?.time_limit_seconds ?? 5} onChange={e => update('options', { ...record.options, time_limit_seconds: Number(e.target.value) })}/></label>
          <label>Deterministic seed<input type="number" min={0} max={2147483647} value={record.options?.seed ?? 42} onChange={e => update('options', { ...record.options, seed: Number(e.target.value) })}/></label>
          <LockedAssignmentsEditor snapshot={snapshot} value={locks} onChange={changeLocks}/>
          {appMode === 'institutional' ? <p className="muted">Manage individual names, IDs, contact emails and section assignments in the Admin Student roster. Use this form only for period-wide constraints.</p> : <label>Explicit synthetic cross-section enrollment conflicts JSON<textarea rows={5} value={enrollments} onChange={e => setEnrollments(e.target.value)}/><p className="muted">Synthetic test identities only. No institutional roster is inferred or imported.</p></label>}
        </details>
      </>}
      {'active' in record && check('Active in this academic period', 'active', record.active)}
    </fieldset>
    {error && <p role="alert" className="academic-field-error">{error}</p>}
    {error && onReload && <><Button type="button" variant="secondary" onClick={onReload}>Reload saved records</Button><p className="muted">Reload discards this unsaved form and retrieves the server-confirmed records.</p></>}
    <div className="draft-actions"><Button type="submit" disabled={busy} loading={busy}>{busy ? 'Saving academic record…' : 'Save Record'}</Button><Button type="button" variant="secondary" disabled={busy} onClick={onCancel}>Cancel</Button></div>
    <p className="muted">Existing generated drafts keep their original snapshots. Current-record edits do not rewrite them.</p>
  </form>;
}
