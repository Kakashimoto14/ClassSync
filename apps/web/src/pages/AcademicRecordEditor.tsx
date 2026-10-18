import { useRef, useState, type FormEvent } from 'react';
import { Button } from '../components/ui/Button';
import type { SessionPattern, Window } from '../../../../packages/shared-types/src/scheduling';
import { saveAcademicRecord, type AcademicKind, type AcademicRecord, type AcademicSnapshot } from '../lib/academic-api';
import { academicLabel, academicRecords } from '../lib/academic-labels';

const dayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const clock = (minute: number) => `${String(Math.floor(minute / 60)).padStart(2, '0')}:${String(minute % 60).padStart(2, '0')}`;
const minutes = (value: string) => { const [h, m] = value.split(':').map(Number); return h * 60 + m; };
const comma = (text: string) => text.split(',').map(v => v.trim()).filter(Boolean);

function CommaField({ label, initial, onChange }: { label: string; initial: string; onChange: (text: string) => void }) {
  const [text, setText] = useState(initial);
  return <label>{label}<input value={text} onChange={e => { setText(e.target.value); onChange(e.target.value); }}/></label>;
}

export function WeeklyWindows({ label, value, onChange }: { label: string; value: Window[]; onChange: (value: Window[]) => void }) {
  return <fieldset className="academic-windows"><legend>{label}</legend>
    {!value.length && <p className="muted">No windows supplied.</p>}
    {value.map((w, i) => <div className="academic-window" key={i}>
      <label>Day<select aria-label={`${label} day ${i + 1}`} value={w.day} onChange={e => onChange(value.map((v, n) => n === i ? { ...v, day: Number(e.target.value) } : v))}>{dayNames.map((d, n) => <option value={n} key={d}>{d}</option>)}</select></label>
      <label>Start<input aria-label={`${label} start ${i + 1}`} type="time" step={1800} required value={clock(w.start)} onChange={e => onChange(value.map((v, n) => n === i ? { ...v, start: minutes(e.target.value) } : v))}/></label>
      <label>End<input aria-label={`${label} end ${i + 1}`} type="time" step={1800} required disabled={w.end === 1440} value={clock(w.end % 1440)} onChange={e => onChange(value.map((v, n) => n === i ? { ...v, end: minutes(e.target.value) } : v))}/></label>
      <Button type="button" variant="ghost" aria-label={`Remove ${label.toLowerCase()} window ${i + 1}`} onClick={() => onChange(value.filter((_, n) => n !== i))}>Remove</Button>
      <label className="academic-checkbox"><input type="checkbox" aria-label={`${label} ends at midnight ${i + 1}`} checked={w.end === 1440} onChange={e => onChange(value.map((v,n) => n === i ? { ...v, end: e.target.checked ? 1440 : 720 } : v))}/>Ends at midnight</label>
      {w.end <= w.start && <p className="academic-field-error">End must be later than start.</p>}
    </div>)}
    <Button type="button" variant="secondary" onClick={() => onChange([...value, { day: 0, start: 480, end: 720 }])}>Add {label.toLowerCase()} window</Button>
    <p className="muted">30-minute boundaries. New rows are visible entry defaults; confirm the actual allowed times before saving.</p>
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
  if (kind === 'offerings') return { ...base, kind, subject_id: '', section_id: '', teacher_ids: [], room_ids: [] };
  return { id: 'rules', kind, operating_windows: [], options: { time_limit_seconds: 15, seed: 42 } };
}

export function AcademicRecordEditor({ kind, snapshot, existing, onSaved, onCancel, onReload }: {
  kind: AcademicKind; snapshot: AcademicSnapshot; existing?: AcademicSnapshot['records'][number]; onSaved: (snapshot: AcademicSnapshot) => void; onCancel: () => void; onReload?: () => void;
}) {
  const [record, setRecord] = useState<AcademicRecord>(() => existing ? structuredClone(existing.record) as AcademicRecord : initialRecord(kind, snapshot.period.id));
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [locks, setLocks] = useState(() => JSON.stringify(record.kind === 'constraints' ? record.locked_assignments ?? [] : [], null, 2));
  const [enrollments, setEnrollments] = useState(() => JSON.stringify(record.kind === 'constraints' ? record.enrollments ?? [] : [], null, 2));
  const active = useRef(false);
  const update = (name: string, value: unknown) => setRecord(r => ({ ...r, [name]: value }) as AcademicRecord);
  const choices = (k: AcademicKind) => academicRecords(snapshot, k).map(r => ({ id: r.id, label: academicLabel(r, snapshot) }));
  const text = (label: string, name: string, value: string | null | undefined, required = false, disabled = false) => <label>{label}<input name={name} required={required} disabled={disabled} value={value ?? ''} onChange={e => update(name, e.target.value || (required ? '' : null))}/></label>;
  const number = (label: string, name: string, value: number | null | undefined, step = 1, min = 0) => <label>{label}<input name={name} type="number" min={min} step={step} value={value ?? ''} onChange={e => update(name, e.target.value === '' ? null : Number(e.target.value))}/></label>;
  const check = (label: string, name: string, value: boolean | undefined) => <label className="academic-checkbox"><input type="checkbox" checked={value ?? false} onChange={e => update(name, e.target.checked)}/>{label}</label>;
  async function submit(event: FormEvent) {
    event.preventDefault(); if (active.current) return;
    active.current = true; setBusy(true); setError('');
    try {
      const next = record.kind === 'constraints' ? { ...record, locked_assignments: JSON.parse(locks), enrollments: JSON.parse(enrollments) } : record;
      if (next.kind === 'subjects' && next.required_weekly_minutes == null) throw new Error('Enter required weekly contact minutes.');
      if (next.kind === 'subjects' && (!next.patterns?.length || next.patterns.some(p => p.durations.reduce((a, b) => a + b, 0) !== next.required_weekly_minutes))) throw new Error('Allowed meeting patterns must total the required weekly contact minutes.');
      onSaved(await saveAcademicRecord(snapshot.period.id, { expected_revision: existing?.revision ?? 0, record: next }));
    } catch (e) { setError(e instanceof Error ? e.message : 'Record save failed.'); }
    finally { active.current = false; setBusy(false); }
  }
  const program = record.kind === 'sections' ? academicRecords(snapshot, 'programs').find(p => p.id === record.program_id) : undefined;
  const customSection = program?.kind === 'programs' && program.section_policy === 'custom';
  const cdm = record.kind === 'resources' && record.id.startsWith('cdm-');
  return <form className="workspace-card academic-record-form" onSubmit={submit} aria-label={`${existing ? 'Edit' : 'New'} ${kind} record`} aria-busy={busy}>
    <h2>{existing ? 'Edit' : 'New'} {kind === 'faculty' ? 'faculty member' : kind === 'constraints' ? 'scheduling constraints' : kind === 'offerings' ? 'subject offering' : kind.replace(/s$/, '')}</h2>
    <fieldset disabled={busy} className="academic-form-fields">
      {record.kind === 'programs' && <>
        <div className="academic-field-grid">{text('Program acronym', 'acronym', record.acronym, true)}{text('Program name', 'name', record.name, true)}{text('Institute', 'institute', record.institute, true)}</div>
        <label>Section naming policy<select value={record.section_policy ?? 'degree'} onChange={e => update('section_policy', e.target.value)}><option value="degree">Structured year and section letter</option><option value="custom">Program-specific label (for example TCP)</option></select></label>
        <details><summary>Program naming rules</summary><CommaField label="Allowed year levels (optional, comma-separated)" initial={record.allowed_year_levels?.join(', ') ?? ''} onChange={value => update('allowed_year_levels', value.trim() ? comma(value).map(Number) : null)}/><p>No program length or number of sections is assumed.</p></details>
      </>}
      {record.kind === 'subjects' && <>
        <div className="academic-field-grid">{text('Subject code', 'code', record.code, true)}{text('Subject name', 'name', record.name, true)}{number('Required weekly contact minutes', 'required_weekly_minutes', record.required_weekly_minutes, 30, 30)}</div>
        <p className="muted">180 minutes is a proposed default. Contact minutes are not academic credit units.</p>
        <ChoiceList label="Associated programs" options={choices('programs')} value={record.program_ids ?? []} onChange={v => update('program_ids', v)}/>
        <Patterns weekly={record.required_weekly_minutes ?? null} value={record.patterns ?? []} onChange={v => update('patterns', v)}/>
        <details><summary>Classroom requirements</summary>{text('Required room type', 'required_room_type', record.required_room_type)}<CommaField label="Required equipment (comma-separated)" initial={record.required_equipment?.join(', ') ?? ''} onChange={value => update('required_equipment', comma(value))}/>{number('Minimum classroom capacity', 'minimum_capacity', record.minimum_capacity, 1, 1)}</details>
      </>}
      {record.kind === 'sections' && <>
        <label>Program<select required value={record.program_id} onChange={e => { update('program_id', e.target.value); update('custom_label', null); }}><option value="">Choose program</option>{choices('programs').map(p => <option key={p.id} value={p.id}>{p.label}</option>)}</select></label>
        {customSection ? text('Program-specific section label', 'custom_label', record.custom_label, true) : <div className="academic-field-grid">{number('Year level', 'year_level', record.year_level, 1, 1)}<label>Section identifier<input required pattern="[A-Z]{1,3}" value={record.section_letter ?? ''} placeholder="A" onChange={e => update('section_letter', e.target.value.toUpperCase())}/></label></div>}
        <p className="muted">Belongs to {snapshot.period.title}. Section identifiers are separate from stable database IDs.</p>
        <details><summary>Verified student population</summary>{number('Student population', 'population', record.population, 1, 1)}{check('Population is verified', 'population_verified', record.population_verified)}</details>
      </>}
      {record.kind === 'faculty' && <>
        <div className="academic-field-grid">{text('Faculty name', 'name', record.name, true)}{text('Institutional faculty identifier (optional)', 'institutional_id', record.institutional_id)}</div>
        <ChoiceList label="Eligible teaching subjects" options={choices('subjects')} value={record.subject_ids ?? []} onChange={v => update('subject_ids', v)}/>
        <WeeklyWindows label="Faculty availability" value={record.availability ?? []} onChange={v => update('availability', v)}/>
        <details><summary>Workload and unavailable times</summary><div className="academic-field-grid">{number('Maximum weekly teaching minutes', 'max_weekly_minutes', record.max_weekly_minutes, 30)}{number('Maximum daily teaching minutes', 'max_daily_minutes', record.max_daily_minutes, 30)}</div><WeeklyWindows label="Faculty unavailable" value={record.unavailable ?? []} onChange={v => update('unavailable', v)}/></details>
        {existing && <p>Referenced by {academicRecords(snapshot, 'offerings').filter(o => o.kind === 'offerings' && o.teacher_ids?.includes(record.id)).length} offerings in this period. Manage assignments in Subject Offerings.</p>}
      </>}
      {record.kind === 'resources' && <>
        {cdm && <p className="scheduling-boundary">CdM provisional identity and location are preserved. Metadata assertions apply to this academic period and do not change existing drafts or the source inventory.</p>}
        <div className="academic-field-grid">{text('Resource name', 'name', record.name, true, cdm)}{text('Building or area', 'building', record.building, true, cdm)}{text('Floor (if supplied)', 'floor', record.floor, false, cdm)}</div>
        {record.alias && <p>{record.alias}{record.alias_unconfirmed ? ' · unconfirmed label' : ''}</p>}
        <label>Known operational condition<select value={record.condition ?? 'unknown'} onChange={e => update('condition', e.target.value)}><option value="unknown">Unknown / unverified</option><option value="operational">Confirmed operational</option><option value="maintenance">Maintenance / unavailable</option></select></label>
        {check('Explicitly eligible for scheduling', 'schedulable', record.schedulable)}
        <div className="academic-field-grid">{text('Room type', 'room_type', record.room_type)}{number('Capacity (if supplied)', 'capacity', record.capacity, 1, 1)}</div>
        {check('Room type is verified', 'type_verified', record.type_verified)}{check('Capacity is verified', 'capacity_verified', record.capacity_verified)}
        <CommaField label="Equipment (comma-separated)" initial={record.equipment?.join(', ') ?? ''} onChange={value => update('equipment', comma(value))}/>{check('Equipment list is verified', 'equipment_verified', record.equipment_verified)}
        <label>Verification source / note<textarea rows={3} value={record.verification_note ?? ''} onChange={e => update('verification_note', e.target.value)}/></label>
        <WeeklyWindows label="Resource availability" value={record.availability ?? []} onChange={v => update('availability', v)}/>
        <details><summary>Resource restrictions</summary><WeeklyWindows label="Resource blocked" value={record.blocked ?? []} onChange={v => update('blocked', v)}/><label className="academic-checkbox"><input type="checkbox" checked={record.allowed_program_ids != null} onChange={e => update('allowed_program_ids', e.target.checked ? [] : null)}/>Restrict to selected programs</label>{record.allowed_program_ids != null && <ChoiceList label="Allowed programs" options={choices('programs')} value={record.allowed_program_ids} onChange={v => update('allowed_program_ids', v)}/>}</details>
      </>}
      {record.kind === 'offerings' && <>
        <label>Subject<select required value={record.subject_id} onChange={e => update('subject_id', e.target.value)}><option value="">Choose subject</option>{choices('subjects').map(s => <option key={s.id} value={s.id}>{s.label}</option>)}</select></label>
        <label>Section<select required value={record.section_id} onChange={e => update('section_id', e.target.value)}><option value="">Choose section</option>{choices('sections').map(s => <option key={s.id} value={s.id}>{s.label}</option>)}</select></label>
        <ChoiceList label="Assigned or eligible faculty" options={choices('faculty')} value={record.teacher_ids ?? []} onChange={v => update('teacher_ids', v)}/>
        <ChoiceList label="Eligible classrooms" options={choices('resources')} value={record.room_ids ?? []} onChange={v => update('room_ids', v)}/>
        <p className="muted">One selected faculty member is assigned for all sessions. Empty selections are incomplete and block readiness. Subject contact-hour patterns apply unless explicitly overridden.</p>
        <details><summary>Offering-specific requirements</summary>{number('Weekly contact-minute override', 'weekly_minutes_override', record.weekly_minutes_override, 30, 30)}
          <label className="academic-checkbox"><input type="checkbox" checked={record.patterns_override != null} onChange={e => { const subject = academicRecords(snapshot, 'subjects').find(s => s.id === record.subject_id); update('patterns_override', e.target.checked && subject?.kind === 'subjects' ? structuredClone(subject.patterns ?? []) : null); }}/>Override allowed meeting patterns</label>
          {record.patterns_override != null && <Patterns weekly={record.weekly_minutes_override ?? (academicRecords(snapshot, 'subjects').find(s => s.id === record.subject_id) as { required_weekly_minutes?: number } | undefined)?.required_weekly_minutes ?? null} value={record.patterns_override} onChange={v => update('patterns_override', v)}/>}
          {text('Required room-type override', 'required_room_type', record.required_room_type)}{number('Minimum capacity override', 'minimum_capacity', record.minimum_capacity, 1, 1)}
          <CommaField label="Additional required equipment" initial={record.required_equipment?.join(', ') ?? ''} onChange={value => update('required_equipment', comma(value))}/><CommaField label="Allowed buildings (optional, comma-separated)" initial={record.allowed_buildings?.join(', ') ?? ''} onChange={value => update('allowed_buildings', value.trim() ? comma(value) : null)}/>
        </details>
      </>}
      {record.kind === 'constraints' && <>
        <WeeklyWindows label="Operating hours" value={record.operating_windows ?? []} onChange={v => update('operating_windows', v)}/>
        <label>Transition buffer<select value={record.transition_buffer_minutes ?? 0} onChange={e => update('transition_buffer_minutes', Number(e.target.value))}>{[0, 30, 60, 90, 120].map(n => <option key={n} value={n}>{n} minutes</option>)}</select></label>
        {check('I have supplied all intended offerings for this period', 'all_intended_offerings_supplied', record.all_intended_offerings_supplied)}
        <p className="muted">This is an administrator scope declaration, not independent verification of school-wide coverage.</p>
        <details><summary>Solver, locked assignments and enrollments</summary>
          <label>Solver time limit (seconds)<input type="number" min={1} max={30} step={1} value={record.options?.time_limit_seconds ?? 5} onChange={e => update('options', { ...record.options, time_limit_seconds: Number(e.target.value) })}/></label>
          <label>Deterministic seed<input type="number" min={0} max={2147483647} value={record.options?.seed ?? 42} onChange={e => update('options', { ...record.options, seed: Number(e.target.value) })}/></label>
          <label>Existing locked assignments JSON<textarea rows={5} value={locks} onChange={e => setLocks(e.target.value)}/></label>
          <label>Explicit cross-section enrollments JSON<textarea rows={5} value={enrollments} onChange={e => setEnrollments(e.target.value)}/></label>
          <p className="muted">Use stable record IDs. All references and locked placements are validated. No student enrollment is inferred.</p>
        </details>
      </>}
      {'active' in record && check('Active in this academic period', 'active', record.active)}
    </fieldset>
    {error && <p role="alert" className="academic-field-error">{error}</p>}
    {error && onReload && <><Button type="button" variant="secondary" onClick={onReload}>Reload saved records</Button><p className="muted">Reload discards this unsaved form and retrieves the server-confirmed records.</p></>}
    <div className="draft-actions"><Button type="submit" disabled={busy}>{busy ? 'Saving academic record…' : 'Save Record'}</Button><Button type="button" variant="secondary" disabled={busy} onClick={onCancel}>Cancel</Button></div>
    <p className="muted">Existing generated drafts keep their original snapshots. Current-record edits do not rewrite them.</p>
  </form>;
}
