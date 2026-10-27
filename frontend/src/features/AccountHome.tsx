import { Link } from 'react-router-dom';
import { FolderOpen, ShieldCheck } from 'lucide-react';
import { type User, label } from '../lib/api';
import { useData, ErrorBox, Heading, Loading } from '../components/ui';

export default function AccountHome({ user }: { user: User }) {
  const query = useData<{ total: number; active: number; closed: number; unread_alerts: number }>('/account/summary');
  return <><Heading eyebrow="YOUR PERSONAL WORKSPACE" title={`Welcome, ${user.name}`} description="Your records and activity, together in one place." />
    {user.approval_pending && <div className="notice"><ShieldCheck size={20} /><div><strong>Access request awaiting approval</strong><p>You requested {label(user.requested_role || '')} access{user.organization ? ` for ${user.organization}` : ''}. An administrator must approve your role and scope. You can manage your account security while you wait.</p></div></div>}
    <ErrorBox error={query.error} retry={() => query.refetch()} />{query.isPending ? <Loading /> : query.data && <><div className="stats">{[['Total cases', query.data.total], ['Active cases', query.data.active], ['Closed cases', query.data.closed], ['Unread alerts', query.data.unread_alerts]].map(([title, count]) => <section className="card stat-card" key={title}><div>{title}</div><strong>{count}</strong><p>From your account records</p></section>)}</div>
    <section className="card account-start"><FolderOpen size={34} /><h2>{query.data.total ? 'Your case records' : 'A fresh start'}</h2><p>{query.data.total ? 'View the cases shared with your account.' : 'You have no cases yet. Records will appear here when they are shared with your account.'}</p><div className="button-row">{!user.approval_pending && <Link className="button primary" to="/complaints">View my cases</Link>}<Link className="button secondary" to="/account-security">Manage account security</Link></div></section></>}
  </>;
}
