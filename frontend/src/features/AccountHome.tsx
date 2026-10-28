import { Link } from 'react-router-dom';
import { FolderOpen, ShieldCheck } from 'lucide-react';
import { type User, label } from '../lib/api';
import { useData, ErrorBox, Heading, Loading } from '../components/ui';
import ComplaintIntake from './ComplaintIntake';

export default function AccountHome({ user }: { user: User }) {
  const query = useData<{ total: number; active: number; closed: number; unread_alerts: number }>('/account/summary');
  return <><Heading eyebrow="YOUR PERSONAL WORKSPACE" title={`Welcome, ${user.name}`} description="Your records and activity, together in one place." action={user.capabilities.submit_complaint ? <a className="button primary" href="#register-complaint">Register complaint</a> : undefined} />
    {user.approval_pending && <div className="notice"><ShieldCheck size={20} /><div><strong>Access request awaiting approval</strong><p>You requested {label(user.requested_role || '')} access{user.organization ? ` for ${user.organization}` : ''}. An administrator must approve your role and scope. You can manage your account security while you wait.</p></div></div>}
    {user.faculty_name && <section className="card intake-card"><h2>Your faculty and enrolment</h2><dl className="detail-grid"><div><dt>Faculty contact</dt><dd>{user.faculty_name}</dd></div><div><dt>Admission / pass-out year</dt><dd>{user.admission_year || 'Not recorded'} / {user.passout_year || 'Not recorded'}</dd></div></dl>{user.is_demo && <p className="muted">Your demo complaints stay within OneCase Demonstration Institute and go to its appointed Demo Faculty for initial review.</p>}</section>}
    <ErrorBox error={query.error} retry={() => query.refetch()} />{query.isPending ? <Loading /> : query.data && <><div className="stats">{[['Total cases', query.data.total], ['Active cases', query.data.active], ['Closed cases', query.data.closed], ['Unread alerts', query.data.unread_alerts]].map(([title, count]) => <section className="card stat-card" key={title}><div>{title}</div><strong>{count}</strong><p>From your account records</p></section>)}</div>
    <section className="card account-start"><FolderOpen size={34} /><h2>{user.roles.includes('faculty_reviewer') ? 'Your complaints and assigned reviews' : query.data.total ? 'Your case records' : 'A fresh start'}</h2><p>{user.roles.includes('faculty_reviewer') ? 'Open complaints appointed to you and send your initial report to the officer. You can also follow your own submissions.' : query.data.total ? 'View your submitted complaints and follow their action history.' : user.capabilities.submit_complaint ? 'You have no complaints yet. Register your first complaint below.' : 'Complaint submission is available to students, parents, institution staff, faculty and other public users.'}</p><div className="button-row">{!user.approval_pending && <Link className="button primary" to="/complaints">View my complaints</Link>}<Link className="button secondary" to="/account-security">Manage account security</Link></div></section></>}
    {user.capabilities.submit_complaint && <ComplaintIntake user={user} />}
  </>;
}
