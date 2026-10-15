import { ArrowLeft, Bot, Building2, CalendarDays, Check, ClipboardCheck, FileSearch, ShieldAlert } from 'lucide-react';
import { Link } from 'react-router-dom';
import { StatusBadge } from '../components/ui/StatusBadge';
import { dashboardPath, type PlannedFeature } from '../routes/route-config';
import type { UserRole } from '../types/ui';

const details = {
  'registration-scanner': { title: 'Registration Form Scanner', description: 'Help students—especially those taking subjects across different sections—review enrollment details and find the schedules that apply to them.', back: '/student/schedule', backLabel: 'Back to My Schedule', icon: FileSearch },
  'ai-conflict-detection': { title: 'AI Conflict Detection', description: 'Future AI assistance will explain detected conflicts, surface affected records, and help administrators compare possible resolutions.', back: '/admin/conflicts', backLabel: 'Back to Conflict Center', icon: ShieldAlert },
  'ai-scheduling': { title: 'AI-Powered Scheduling', description: 'Assist administrators in preparing timetable candidates while honoring mandatory institutional and resource constraints.', back: '/admin/schedule-manager', backLabel: 'Back to Schedule Manager', icon: CalendarDays },
  'institutional-rules': { title: 'Institutional Scheduling Rules', description: 'Give authorized administrators a configurable place to maintain program, subject, section, building, and room assignment rules.', back: '/admin/settings', backLabel: 'Back to Settings', icon: Building2 },
} as const;

const scannerSteps = ['Select a supported form (future capability)', 'Review extracted subject codes, names, and sections', 'Correct ambiguous or missing details', 'Confirm the mapping before schedules are matched'];
const schedulingSteps = ['Choose academic year, semester, and scope', 'Review source data, availability, and institutional rules', 'Generate candidate timetables (planned)', 'Run deterministic validation, then compare and approve'];

export function ComingSoonPage({ feature, role }: { feature: PlannedFeature; role: UserRole }) {
  const item = details[feature];
  const Icon = item.icon;
  return <section className="coming-soon-page">
    <div className="page-heading"><div><p className="eyebrow">{role === 'administrator' ? 'Administrator' : 'Student'} · Planned capability</p><h1>{item.title}</h1><p>{item.description}</p></div><StatusBadge tone="info">Coming Soon</StatusBadge></div>
    <section className="workspace-card coming-soon-card">
      <div className="coming-soon-card__intro"><span className="coming-soon-icon"><Icon size={24}/></span><div><StatusBadge tone="info">Coming Soon</StatusBadge><h2>This capability is not available yet</h2><p>Nothing is being uploaded, analyzed, generated, saved, or published in this preview.</p></div></div>
      {feature === 'registration-scanner' && <div className="feature-preview">
        <h3>Planned student workflow</h3><p>The scanner is intended to help identify enrolled subjects and sections from registration documents and OVRFs, including irregular subject combinations.</p>
        <ol className="feature-steps">{scannerSteps.map((step, index) => <li key={step}><span>{index + 1}</span>{step}</li>)}</ol>
        <div className="feature-note"><FileSearch size={18}/><p>Future extraction will account for varied PDF and image layouts, low quality, duplicates, missing codes, and ambiguous sections. Extracted, review-needed, corrected, and confirmed values will remain distinct. No sample student record or upload control is shown.</p></div>
      </div>}
      {feature === 'ai-conflict-detection' && <div className="feature-preview">
        <h3>Conflict → explanation → candidate resolutions → administrator review</h3>
        <p className="illustrative-label">Illustrative example only · no AI analysis has been performed</p>
        <div className="conflict-example"><div><StatusBadge tone="danger">Room/time overlap</StatusBadge><strong>Two classes are assigned to SCI-108</strong><span>Tuesday · 10:00–11:30 · sample records</span></div><ArrowLeft size={18} className="example-arrow"/><div><Bot size={19}/><strong>Future explanation</strong><span>A shared room and overlapping times may prevent both classes from meeting as scheduled.</span></div></div>
        <div className="resolution-grid"><article><StatusBadge tone="neutral">Candidate A · illustrative</StatusBadge><strong>Use ENG-204 at the same time</strong><p>Trade-off: confirm suitable capacity, facilities, and program/building rules.</p></article><article><StatusBadge tone="neutral">Candidate B · illustrative</StatusBadge><strong>Move one class to a free period</strong><p>Trade-off: recheck teacher and section availability and class preferences.</p></article></div>
        <div className="feature-note"><ShieldAlert size={18}/><p>Mandatory conflicts must be checked by deterministic server-side rules. AI may explain or recommend only; an administrator reviews and approves official schedule changes.</p></div>
      </div>}
      {feature === 'ai-scheduling' && <div className="feature-preview">
        <h3>Planned recommendation workflow</h3><ol className="feature-steps">{schedulingSteps.map((step, index) => <li key={step}><span>{index + 1}</span>{step}</li>)}</ol>
        <div className="feature-columns"><article><h4>Hard constraints</h4><p>Teacher, section, and room overlaps; capacity; room status; availability; required facilities; institutional assignment rules.</p></article><article><h4>Soft preferences</h4><p>Teacher preferences, shorter gaps, fewer room changes, balanced utilization, and preferred time periods.</p></article></div>
        <div className="feature-note"><Check size={18}/><p>A recommendation is not a validated schedule. Server-side deterministic validation must pass hard rules before authorized administrators can approve and publish.</p></div>
      </div>}
      {feature === 'institutional-rules' && <div className="feature-preview">
        <h3>Configurable rule examples</h3><p className="illustrative-label">Illustrative only · these are not ClassSync defaults or institutional policy</p>
        <div className="rule-example-grid"><article><Building2 size={19}/><strong>Old Building</strong><span>Example permitted programs: ICS programs such as BSIT and BSCpE.</span></article><article><Building2 size={19}/><strong>New Building</strong><span>Example permitted programs: BSED, BSBA, BTLED, and other institution-approved programs.</span></article></div>
        <div className="feature-columns"><article><h4>Possible rule dimensions</h4><p>Academic unit, program, subject, section, building, room/type, facilities, capacity, period, and academic year/semester.</p></article><article><h4>Governance</h4><p>Priority, effective dates, enabled state, visible authorized exceptions, approval, and audit history.</p></article></div>
        <div className="feature-note"><ClipboardCheck size={18}/><p>Conflicting rules must be resolved explicitly. A prohibited building is never silently assigned; if no eligible room exists, the future workflow must explain why.</p></div>
      </div>}
      <div className="coming-soon-actions"><Link className="button button--secondary" to={item.back}><ArrowLeft size={16}/>{item.backLabel}</Link><Link className="text-action" to={dashboardPath(role)}>Return to dashboard</Link></div>
    </section>
  </section>;
}
