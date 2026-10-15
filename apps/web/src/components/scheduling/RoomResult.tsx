import { ArrowUpRight, MonitorCheck, Users } from 'lucide-react';
import { Link } from 'react-router-dom';
import { StatusBadge } from '../ui/StatusBadge';
import type { UserRole } from '../../types/ui';
import { rolePath } from '../../routes/route-config';
export function RoomResult({ role }: { role: UserRole }) { return <section className="room-result"><div><p className="eyebrow">Room availability</p><h2>Suggested classroom</h2><p className="muted">Available for the selected period · 42 seats · projector and lab PCs.</p></div><article className="room-card"><div><strong>SCI-218</strong><span>Science building · Level 2</span></div><StatusBadge tone="success">Available</StatusBadge><div className="room-facts"><span><Users size={16}/>42 seats</span><span><MonitorCheck size={16}/>Projector, lab PCs</span></div><Link className="text-action" to={rolePath(role, role === 'administrator' ? 'availability' : 'find-room')}>View room options <ArrowUpRight size={16}/></Link></article></section>; }
