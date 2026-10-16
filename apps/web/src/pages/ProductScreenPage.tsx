import { useState } from 'react';
import { Building2, CalendarDays, ClipboardList, FileBarChart, MapPin, Search, ShieldAlert } from 'lucide-react';
import { Link } from 'react-router-dom';
import { AppShell } from '../components/layout/AppShell';
import { RoomDirectoryCard } from '../components/scheduling/RoomDirectoryCard';
import { Alert } from '../components/ui/Alert';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { StatusBadge } from '../components/ui/StatusBadge';
import { rolePath, type RouteDefinition } from '../routes/route-config';

const classes = [
  { time: '08:00 AM', subject: 'Human Computer Interaction', section: 'BSIT 2A', teacher: 'Prof. Avery Cruz', room: 'Room 405', building: 'New Building · Floor 4', tone: 'success' as const, status: 'Confirmed' },
  { time: '10:00 AM', subject: 'Database Management Systems', section: 'BSIT 2A', teacher: 'Prof. Maria Santos', room: 'Room 301', building: 'Old Building · Floor 3', tone: 'success' as const, status: 'Confirmed' },
  { time: '01:00 PM', subject: 'Information Assurance', section: 'BSIT 2A', teacher: 'Prof. Daniel Reyes', room: 'Computer Lab 2', building: 'Old Building · Floor 2', tone: 'warning' as const, status: 'Room update' },
];
const rooms = [
  { id: 'SCI-218', building: 'Science Building', floor: 'Level 2', type: 'Computer laboratory', seats: 42, facilities: 'Projector · Lab PCs · Internet', status: 'Available' },
  { id: 'ENG-204', building: 'Engineering Building', floor: 'Level 2', type: 'Lecture room', seats: 40, facilities: 'Projector · Whiteboard', status: 'Available' },
  { id: 'LAB-04', building: 'Computing Building', floor: 'Level 1', type: 'Computer laboratory', seats: 28, facilities: 'Lab PCs · Internet', status: 'Maintenance' },
];

export function ProductScreenPage({ definition }: { definition: RouteDefinition }) {
  return <AppShell><div className="page-heading"><div><p className="eyebrow">{definition.navigationGroup ?? (definition.role === 'administrator' ? 'Administrator' : definition.role)}</p><h1>{definition.title}</h1><p>{definition.description}</p></div>{definition.kind === 'schedule' && definition.role === 'administrator' && <Link className="button" to="/admin/schedule-manager/create">Create schedule</Link>}</div>
    {definition.kind === 'schedule' && <ScheduleScreen definition={definition}/>}
    {definition.kind === 'schedule-create' && <CreateScheduleScreen/>}
    {definition.kind === 'calendar' && <CalendarScreen definition={definition}/>}
    {definition.kind === 'conflicts' && <ConflictScreen/>}
    {definition.kind === 'conflict-detail' && <ConflictDetailScreen/>}
    {definition.kind === 'requests' && <RequestScreen role={definition.role}/>}
    {definition.kind === 'request-create' && <RequestCreateScreen/>}
    {definition.kind === 'request-detail' && <RequestDetailScreen role={definition.role}/>}
    {definition.kind === 'report-issue' && <IssueReportScreen/>}
    {definition.kind === 'rooms' && <RoomScreen definition={definition}/>}
    {definition.kind === 'room-detail' && <RoomDetailScreen/>}
    {definition.kind === 'buildings' && <BuildingScreen/>}
    {definition.kind === 'building-detail' && <BuildingDetailScreen/>}
    {definition.kind === 'academic-list' && <AcademicListScreen definition={definition}/>}
    {definition.kind === 'academic-detail' && <AcademicDetailScreen/>}
    {definition.kind === 'reports' && <ReportScreen utilization={definition.id.endsWith('.utilization')}/>}
    {definition.kind === 'notifications' && <NoticeScreen/>}
    {definition.kind === 'announcements' && <AnnouncementScreen role={definition.role}/>}
    {definition.kind === 'profile' && <ProfileScreen role={definition.role}/>}
    {definition.kind === 'settings' && <SettingsScreen/>}
    {definition.kind === 'audit' && <AuditScreen/>}
  </AppShell>;
}

function ScheduleScreen({ definition }: { definition: RouteDefinition }) {
  const isAdmin = definition.role === 'administrator'; const isTeacher = definition.role === 'teacher';
  return <section className="workspace-card">
    {isAdmin ? <><div className="admin-schedule-filters"><label>Week of<input type="date" defaultValue="2026-09-21"/></label><label>Teacher<select defaultValue="all"><option value="all">All teachers</option><option>Prof. Santos</option></select></label><label>Section<select defaultValue="all"><option value="all">All sections</option><option>BSIT 2A</option></select></label><label>Room<select defaultValue="all"><option value="all">All rooms</option><option>SCI-108</option></select></label><label>Status<select defaultValue="all"><option value="all">All states</option><option>Draft</option><option>Published</option></select></label></div><div className="schedule-tabs"><strong>Week</strong><span>Day</span><span>Month</span><StatusBadge tone="neutral">2 drafts</StatusBadge></div></> : <div className="schedule-tabs"><strong>This week · September 21–25</strong><span>Today</span><StatusBadge tone="info">{isTeacher ? 'Teaching assignments' : 'Personal timetable'}</StatusBadge></div>}
    <div className="personal-schedule">{classes.map(item => <article className="personal-class" key={item.time}><time>{item.time}</time><div className="class-accent"/><div className="class-content"><strong>{item.subject}</strong><span>{isAdmin ? `Section ${item.section} · ${item.teacher}` : isTeacher ? `Section ${item.section}` : `Section ${item.section} · ${item.teacher}`}</span><span><MapPin size={14}/>{item.room} · {item.building}</span></div><StatusBadge tone={item.tone}>{item.status}</StatusBadge>{isTeacher && <Link className="text-action" to={rolePath('teacher', 'requests')}>Request room change</Link>}{isAdmin && <Link className="text-action" to={rolePath('administrator', 'conflicts')}>Review</Link>}</article>)}</div>
    {!isAdmin && <section className="schedule-export" aria-labelledby="schedule-export-heading"><div><h2 id="schedule-export-heading">Export Schedule</h2><p>Calendar downloads are snapshots; later schedule changes will not synchronize automatically.</p></div><Button type="button" variant="secondary" disabled aria-describedby="schedule-export-unavailable">Export Schedule</Button><div id="schedule-export-unavailable" className="schedule-export__unavailable" role="status">Export unavailable in this preview: the displayed schedule does not include authoritative event dates and end times. ClassSync will not create a calendar file from incomplete data.</div></section>}
    {isAdmin && <div className="schedule-admin-footer"><Alert tone="warning" title="One schedule conflict needs review">SCI-108 is assigned to two classes on Tuesday at 10:00 AM.</Alert><Link className="button button--secondary" to={rolePath('administrator', 'conflicts')}>Review conflicts</Link></div>}
  </section>;
}

function CreateScheduleScreen() { return <form className="workspace-card request-form" onSubmit={event => event.preventDefault()}><h2>Class information</h2><div className="form-grid"><label>Subject<select defaultValue=""><option value="" disabled>Select a subject</option><option>Database Management Systems</option></select></label><label>Section<select defaultValue=""><option value="" disabled>Select a section</option><option>BSIT 2A</option></select></label><label>Teacher<select defaultValue=""><option value="" disabled>Select a teacher</option><option>Prof. Maria Santos</option></select></label><label>Day<input type="text" defaultValue="Tuesday"/></label><label>Start time<input type="time" defaultValue="10:00"/></label><label>End time<input type="time" defaultValue="11:30"/></label><label>Classroom<select defaultValue=""><option value="" disabled>Select a room</option><option>SCI-218</option></select></label></div><section className="validation-checks"><h3>Before publishing</h3><StatusBadge tone="info">Teacher availability</StatusBadge><StatusBadge tone="info">Section availability</StatusBadge><StatusBadge tone="info">Room and capacity</StatusBadge><StatusBadge tone="info">Operating hours</StatusBadge></section><Alert tone="info" title="Server validation required">A schedule cannot be validated or published until the scheduling service checks for conflicts and capacity.</Alert><div className="inline-actions"><Link className="button button--secondary" to="/admin/schedule-manager">Cancel</Link><Button type="button" disabled>Save draft</Button></div></form>; }

function CalendarScreen({ definition }: { definition: RouteDefinition }) { const [month,setMonth]=useState(new Date(2026,8,1)); const title=month.toLocaleDateString('en',{month:'long',year:'numeric'}); const count=new Date(month.getFullYear(),month.getMonth()+1,0).getDate(); const offset=(new Date(month.getFullYear(),month.getMonth(),1).getDay()+6)%7; const cells=[...Array(offset).fill(null),...Array.from({length:count},(_,index)=>index+1)]; return <section className="workspace-card"><div className="calendar-head"><Button variant="secondary" aria-label="Previous month" onClick={()=>setMonth(new Date(month.getFullYear(),month.getMonth()-1,1))}>‹</Button><h2>{title}</h2><Button variant="secondary" aria-label="Next month" onClick={()=>setMonth(new Date(month.getFullYear(),month.getMonth()+1,1))}>›</Button></div><div className="calendar-grid">{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map(day => <strong className="calendar-weekday" key={day}>{day}</strong>)}{cells.map((date,index)=><div className={`calendar-day ${date===23?'calendar-day--active':''}`} key={date??`blank-${index}`}>{date&&<><span>{date}</span>{date===23&&<small>{definition.role==='administrator'?'3 campus classes':'3 classes'}</small>}{date===26&&<small>Room update</small>}</>}</div>)}</div></section>; }

function ConflictScreen() { const [query, setQuery] = useState(''); const matches = (value: string) => value.toLowerCase().includes(query.trim().toLowerCase()); const roomConflict = matches('SCI-108 is assigned to two classes Tuesday 10:00 Science Building Database Management Systems BSIT 2A Web Systems BSCS 1B'); const capacityConflict = matches('Room ENG-204 is close to section capacity Wednesday 1:00 2 seats remaining'); return <><div className="screen-toolbar"><label><Search size={16}/><input placeholder="Search conflicts" aria-label="Search conflicts" value={query} onChange={event => setQuery(event.target.value)}/></label></div><section className="conflict-list">{roomConflict && <article className="conflict-entry"><StatusBadge tone="danger">Room conflict · Critical</StatusBadge><h2>SCI-108 is assigned to two classes</h2><p>Tuesday · 10:00–11:30 · Science Building</p><div className="conflict-pair"><span>Database Management Systems · BSIT 2A</span><span>Web Systems · BSCS 1B</span></div><Link className="button button--secondary" to="/admin/conflicts/detail">View conflict details</Link><Link className="text-action" to="/admin/room-availability">Find another room</Link></article>}{capacityConflict && <article className="conflict-entry"><StatusBadge tone="warning">Capacity review</StatusBadge><h2>Room ENG-204 is close to section capacity</h2><p>Wednesday · 1:00–2:30 · 2 seats remaining</p><Link className="text-action" to="/admin/rooms/detail">Review room details</Link></article>}{!roomConflict && !capacityConflict && <EmptyState title="No matching conflicts" detail="Try a room, class, section, or conflict type."/>}</section></>; }
function ConflictDetailScreen() { return <section className="two-column"><article className="workspace-card"><Alert tone="danger" title="Room conflict · Critical">SCI-108 is assigned to two classes at the same time.</Alert><dl className="detail-list"><dt>When</dt><dd>Tuesday · 10:00–11:30</dd><dt>Where</dt><dd>SCI-108 · Science Building · Level 1</dd><dt>Why</dt><dd>Overlapping scheduled reservations</dd><dt>Conflicting classes</dt><dd>Database Management · BSIT 2A<br/>Web Systems · BSCS 1B</dd></dl><div className="inline-actions"><Link className="button button--secondary" to="/admin/schedule-manager">Review schedule</Link><Link className="button" to="/admin/room-availability">Find available room</Link></div></article><aside className="state-card"><ShieldAlert/><h2>Resolution options</h2><p>Review schedule assignments, select a suitable available room, or adjust the time after validating all affected resources.</p></aside></section>; }

function RequestScreen({ role }: { role: RouteDefinition['role'] }) { const isAdmin = role === 'administrator'; return <section className="workspace-card"><div className="section-head"><div><h2>{isAdmin ? 'Requests awaiting review' : 'Your submitted requests'}</h2><p className="muted">{isAdmin ? 'Official schedules change only after administrator approval.' : 'An administrator reviews requests; submitting does not change your schedule.'}</p></div>{!isAdmin && <Link className="button" to="/teacher/change-requests/new">New request</Link>}</div><div className="request-entry"><StatusBadge tone="warning">Pending review</StatusBadge><strong>Room change · BSIT 2A · Database Management</strong><span>Tuesday · 10:00 AM · SCI-108 → SCI-218</span><p>Reason: Accessibility requirements for this session.</p><div className="inline-actions"><Link className="button button--secondary" to={isAdmin?'/admin/requests/detail':'/teacher/change-requests/detail'}>View request</Link>{isAdmin&&<><Button variant="secondary" disabled>Reject</Button><Button disabled>Approve request</Button></>}</div></div><div className="request-entry"><StatusBadge tone="success">Resolved</StatusBadge><strong>Room change · BSIT 3A · Network Lab</strong><span>Thursday · 1:00 PM · LAB-04 → ENG-204</span></div><EmptyState title={isAdmin ? 'No other requests' : 'No more requests'} detail={isAdmin ? 'New classroom requests will appear here for review.' : 'Your future classroom change requests will appear here.'}/></section>; }
function RequestCreateScreen() { return <section className="workspace-card request-form"><Alert tone="info" title="Administrator review required">A request does not directly edit your official teaching schedule.</Alert><h2>Classroom change request</h2><label>Assigned class<select defaultValue=""><option value="" disabled>Select a class</option><option>Database Management · Tuesday 10:00 AM · SCI-108</option></select></label><label>Suggested room<select defaultValue="SCI-218"><option>SCI-218 · Available · 42 seats</option><option>ENG-204 · Available · 40 seats</option></select></label><label>Reason<textarea rows={4} placeholder="Explain why a room change is needed."/></label><div className="request-flow"><span>Submitted</span><span>Administrator review</span><span>Decision and notification</span></div><div className="inline-actions"><Link className="button button--secondary" to="/teacher/change-requests">Cancel</Link><Button disabled>Submit request</Button></div></section>; }
function RequestDetailScreen({ role }: { role: RouteDefinition['role'] }) { const isAdmin=role==='administrator'; return <section className="two-column"><article className="workspace-card"><StatusBadge tone="warning">Pending review</StatusBadge><h2>Classroom change · BSIT 2A</h2><dl className="detail-list"><dt>Class</dt><dd>Database Management Systems</dd><dt>Current room</dt><dd>SCI-108 · Tuesday 10:00 AM</dd><dt>Suggested room</dt><dd>SCI-218 · 42 seats · projector</dd><dt>Reason</dt><dd>Accessibility requirements for this session.</dd><dt>Status history</dt><dd>Submitted Monday · Awaiting administrator review</dd></dl>{isAdmin?<div className="inline-actions"><Button variant="secondary" disabled>Reject request</Button><Button disabled>Approve and update schedule</Button></div>:<p className="muted">The official schedule remains unchanged until an administrator reviews this request.</p>}</article><aside className="state-card"><ClipboardList/><h2>{isAdmin?'Review request':'Request process'}</h2><p>{isAdmin?'Review the reason and suggested room. Confirm all schedule constraints before approving.':'After review, you will receive a notification with the administrator’s decision.'}</p></aside></section>; }

function IssueReportScreen() { return <form className="workspace-card request-form" onSubmit={event => event.preventDefault()}><h2>Classroom or schedule issue</h2><p className="muted">Reports go to an administrator. They do not change an official schedule.</p><label>Related class<select defaultValue=""><option value="" disabled>Select a class</option><option>Database Management · Tuesday 10:00 AM</option></select></label><label>Issue type<select defaultValue="room"><option value="room">Classroom issue</option><option value="schedule">Schedule conflict</option></select></label><label>Describe the issue<textarea required rows={4} placeholder="Include the room, time, and what needs attention."/></label><Button type="submit" disabled>Submit report</Button></form>; }

function RoomScreen({ definition }: { definition: RouteDefinition }) {
  const availability =
    definition.title.toLowerCase().includes('availability') ||
    definition.title.toLowerCase().includes('available');
  const [building, setBuilding] = useState('all');
  const [capacity, setCapacity] = useState('');
  const [roomType, setRoomType] = useState('all');
  const filteredRooms = rooms.filter(
    (room) =>
      (building === 'all' || room.building === building) &&
      (!capacity || room.seats >= Number(capacity)) &&
      (roomType === 'all' || room.type === roomType),
  );
  return (
    <>
      <div className="screen-toolbar room-filter-toolbar">
        {availability && (
          <>
            <label>
              Date
              <input
                type="date"
                defaultValue="2026-09-23"
                disabled
                aria-describedby="availability-preview-note"
              />
            </label>
            <label>
              Time window
              <input
                type="time"
                defaultValue="10:00"
                disabled
                aria-describedby="availability-preview-note"
              />
            </label>
          </>
        )}
        <label>
          Building
          <select value={building} onChange={(event) => setBuilding(event.target.value)}>
            <option value="all">All buildings</option>
            {[...new Set(rooms.map((room) => room.building))].map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </label>
        <label>
          Minimum capacity
          <input
            type="number"
            min="1"
            value={capacity}
            onChange={(event) => setCapacity(event.target.value)}
            placeholder="Any"
          />
        </label>
        <label>
          Room type
          <select value={roomType} onChange={(event) => setRoomType(event.target.value)}>
            <option value="all">All room types</option>
            {[...new Set(rooms.map((room) => room.type))].map((type) => (
              <option key={type}>{type}</option>
            ))}
          </select>
        </label>
      </div>
      {availability && (
        <p id="availability-preview-note" className="occupancy-note">
          <CalendarDays size={15} />
          Time-window availability is a local preview until live schedule data is connected.
        </p>
      )}
      <section className="room-results">
        {filteredRooms.map((room) => (
          <RoomDirectoryCard
            key={room.id}
            room={room}
            availabilityPreview={availability}
            detailsPath={
              definition.role === 'administrator' && room.id === 'SCI-218'
                ? rolePath('administrator', 'room-detail')
                : undefined
            }
          />
        ))}
      </section>
      {filteredRooms.length === 0 && (
        <EmptyState
          title="No matching rooms"
          detail="Try a different building, capacity, or room type."
        />
      )}
    </>
  );
}

function BuildingScreen() { return <section className="room-results">{['Science Building','Engineering Building','Computing Building'].map((building, index) => <article className="room-directory-card" key={building}><div className="room-thumb"><Building2/></div><div><h2>{building}</h2><p>{index + 2} floors · {8 + index * 3} classrooms</p><div className="room-meta"><span>{12 + index * 4} scheduled rooms</span><span>{4 + index} rooms available today</span></div></div><Link className="button button--secondary" to="/admin/buildings/detail">View building</Link></article>)}</section>; }
function RoomDetailScreen() { return <section className="two-column"><article className="workspace-card"><StatusBadge tone="success">Resource active</StatusBadge><h2>SCI-218 · Computer laboratory</h2><dl className="detail-list"><dt>Building</dt><dd>Science Building · Level 2</dd><dt>Capacity</dt><dd>42 seats</dd><dt>Facilities</dt><dd>Projector · Lab PCs · Internet</dd><dt>Resource status</dt><dd>Available for scheduling</dd></dl><h3>Upcoming schedule</h3><p className="muted">Tuesday · 10:00 AM · No scheduled reservation</p></article><aside className="state-card"><CalendarDays/><h2>Scheduled availability</h2><p>This status is based on schedule records. It does not indicate real time physical occupancy.</p></aside></section>; }
function BuildingDetailScreen() { return <section className="workspace-card"><h2>Science Building</h2><p className="muted">Campus teaching spaces · 3 floors</p><div className="room-results">{rooms.filter(room=>room.building==='Science Building').map(room=><article className="room-directory-card" key={room.id}><div className="room-thumb"><Building2/></div><div><StatusBadge tone={room.status==='Available'?'success':'warning'}>{room.status}</StatusBadge><h2>{room.id}</h2><p>{room.type} · {room.seats} seats</p></div><Link className="button button--secondary" to="/admin/rooms/detail">View room</Link></article>)}</div></section>; }

function AcademicListScreen({ definition }: { definition: RouteDefinition }) { const subject = definition.title === 'Subjects'; const group = definition.title === 'Sections'; const firstColumn = subject ? 'Subject' : group ? 'Section' : definition.title.slice(0, -1); const rows = subject ? ['Database Management Systems','Web Systems','Human Computer Interaction'] : group ? ['BSIT 2A','BSCS 1B','BSIT 3A'] : ['Avery Cruz','Morgan Reyes','Sam Lee']; const [query, setQuery] = useState(''); const [status, setStatus] = useState('all'); const displayedRows = rows.filter((name, index) => name.toLowerCase().includes(query.trim().toLowerCase()) && (status === 'all' || (status === 'attention' ? index === 1 : index !== 1))); return <><div className="screen-toolbar"><label><Search size={16}/><input placeholder={`Search ${definition.title.toLowerCase()}`} aria-label={`Search ${definition.title.toLowerCase()}`} value={query} onChange={event => setQuery(event.target.value)}/></label><label>Status<select value={status} onChange={event => setStatus(event.target.value)}><option value="all">All statuses</option><option value="active">Active</option><option value="attention">Attention</option></select></label></div>{displayedRows.length > 0 ? <><section className="table-wrap"><table><thead><tr><th>{firstColumn}</th><th>{subject ? 'Code' : group ? 'Program · Year' : 'Academic context'}</th><th>Status</th><th>Schedule relation</th><th>Details</th></tr></thead><tbody>{displayedRows.map(name => { const index = rows.indexOf(name); return <tr key={name}><td><strong>{name}</strong></td><td>{subject ? `SUB-${201 + index}` : group ? 'BSIT · Year 2' : 'Academic scheduling'}</td><td><StatusBadge tone={index === 1 ? 'warning' : 'success'}>{index === 1 ? 'Attention' : 'Active'}</StatusBadge></td><td>{index + 1} assigned classes</td><td><Link className="text-action" to="/admin/academic/details">View record</Link></td></tr>; })}</tbody></table></section><div className="mobile-record-list">{displayedRows.map(name => { const index = rows.indexOf(name); return <article key={name}><strong>{name}</strong><span>{subject ? `SUB-${201 + index}` : 'Academic scheduling'}</span><StatusBadge tone={index === 1 ? 'warning' : 'success'}>{index === 1 ? 'Attention' : 'Active'}</StatusBadge></article>; })}</div></> : <EmptyState title={`No matching ${definition.title.toLowerCase()}`} detail="Try another search term or status."/>}</>; }
function AcademicDetailScreen() { return <section className="workspace-card"><p className="eyebrow">Academic record</p><h2>BSIT 2A · Second Year</h2><dl className="detail-list"><dt>Program</dt><dd>Bachelor of Science in Information Technology</dd><dt>Students</dt><dd>35 active students</dd><dt>Adviser</dt><dd>Prof. Maria Santos</dd><dt>Schedule</dt><dd>Published · 18 class periods</dd></dl><h3>Related subjects</h3><ul className="related-list"><li>Database Management Systems</li><li>Web Systems</li><li>Human Computer Interaction</li></ul></section>; }

function ReportScreen({ utilization }: { utilization: boolean }) { return <section className="report-grid"><article className="workspace-card"><p className="eyebrow">{utilization ? 'Scheduled room usage' : 'Schedule health'}</p><h2>{utilization ? 'Room use by weekday' : 'Current academic period'}</h2><div className="bar-chart" aria-label="Representative report chart">{[52,72,45,81,65].map((height,index)=><span style={{height:`${height}%`}} key={index}/>)}</div><p className="muted">Compare scheduled use across rooms and days to support allocation decisions.</p></article><article className="state-card"><FileBarChart/><h2>Report filters</h2><label>Date range<input type="month" defaultValue="2026-09" disabled/></label><label>Building<select defaultValue="all" disabled><option>All buildings</option></select></label><p className="muted">Report exports require connected academic data.</p><Button variant="secondary" disabled>Export report</Button></article></section>; }

function NoticeScreen() { return <section className="notice-list">{[{ title: 'Room change', category: 'Room', body: 'Your class has moved to Room 304.', time: '2 hours ago', unread: true },{title:'Schedule updated',category:'Schedule',body:'The administrator updated a class assignment.',time:'5 hours ago',unread:false},{title:'University announcement',category:'Announcement',body:'Academic scheduling information for this semester.',time:'Yesterday',unread:false}].map(item=><article className={item.unread?'notice-unread':''} key={item.title}><span className="notice-icon"><CalendarDays/></span><div><StatusBadge tone={item.category==='Room'?'warning':'info'}>{item.category}</StatusBadge><h2>{item.title}</h2><p>{item.body}</p><small>{item.time}</small></div>{item.unread&&<span className="unread-dot" aria-label="Unread"/>}</article>)}</section>; }

function AnnouncementScreen({ role }: { role: RouteDefinition['role'] }) { return <section className="notice-list">{['Academic schedule release','Classroom maintenance notice','Semester timetable reminder'].map((title,index)=><article key={title}><span className="notice-icon"><CalendarDays/></span><div><StatusBadge tone="info">{index===0?'Academic':'Room'}</StatusBadge><h2>{title}</h2><p>Information relevant to current classroom schedules and availability.</p><small>{index+1} days ago</small></div>{role==='administrator'&&<span className="status status--neutral">Editing unavailable</span>}</article>)}</section>; }

function ProfileScreen({ role }: { role: RouteDefinition['role'] }) { const data = role==='student'?['Maria Santos','Student','BSIT 2A · Second Year']:role==='teacher'?['Prof. Santos','Teacher','Information Technology']:['Admin User','Administrator','Academic Operations']; return <section className="workspace-card profile-card"><span className="avatar profile-avatar">{data[0].split(' ').map(part=>part[0]).join('')}</span><div><p className="eyebrow">{data[1]}</p><h2>{data[0]}</h2><p>{data[2]}</p></div><dl className="detail-list"><dt>Account</dt><dd>University account</dd><dt>Schedule access</dt><dd>{role==='student'?'Published schedules':role==='teacher'?'Assigned teaching schedules':'Scheduling administration'}</dd></dl><Link className="button button--secondary" to={rolePath(role,'settings')}>Account settings</Link></section>; }

function SettingsScreen() { return <section className="workspace-card settings-card"><h2>Preferences</h2><Alert tone="info" title="Settings preview">Notification preferences are shown for interface review only; this local demo does not save account settings.</Alert><div className="settings-row"><div><strong>Schedule notifications</strong><p>Receive updates about room and time changes.</p></div><input type="checkbox" checked readOnly disabled aria-label="Schedule notifications unavailable in this preview"/></div><div className="settings-row"><div><strong>Announcement notifications</strong><p>Receive important university scheduling notices.</p></div><input type="checkbox" checked readOnly disabled aria-label="Announcement notifications unavailable in this preview"/></div><div className="settings-row"><div><strong>Account security</strong><p>Production sign-in and account security are not configured in this local demo.</p></div><span className="status status--neutral">Development preview</span></div></section>; }

function AuditScreen() { return <><div className="screen-toolbar"><label><Search size={16}/><input placeholder="Search audit events" aria-label="Search audit events"/></label></div><section className="table-wrap"><table><thead><tr><th>Event</th><th>Actor</th><th>Resource</th><th>Time</th></tr></thead><tbody>{['Schedule published','Classroom request approved','Room marked under maintenance'].map((name,index)=><tr key={name}><td><strong>{name}</strong></td><td>Admin User</td><td>{index===1?'BSIT 2A request':'Academic schedule'}</td><td>{index+1} hours ago</td></tr>)}</tbody></table></section></>; }
