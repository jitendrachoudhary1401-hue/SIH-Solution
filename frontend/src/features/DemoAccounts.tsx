import { useId, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { ArrowRight, ChevronDown, Users } from 'lucide-react';
import { api, post, finishPendingLogout, label, type User } from '../lib/api';
import { Loading, ErrorBox } from '../components/ui';

type Identity = {user: User; csrf: string};
const descriptions: Record<string, string> = {
  faculty_reviewer: 'Review an appointed complaint and send a report to its officer',
  student: 'A personal student workspace', parent: 'Follow records shared with a parent', faculty: 'A faculty member’s personal workspace',
  staff: 'An institution staff workspace', other: 'A community member’s workspace', officer: 'Receive and coordinate demo cases',
  lead: 'Manage a demonstration bureau', reviewer: 'Review potential case relationships', committee: 'Access appointed proceedings',
  verifier: 'Review compliance evidence', executive: 'Explore scoped monitoring', auditor: 'View scoped records and reports',
};

export default function DemoAccounts({onSuccess}: {onSuccess: (identity: Identity) => void}) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const query = useQuery({queryKey: ['demo-accounts'], enabled: open, retry: false,
    queryFn: () => api<{enabled: boolean; accounts: {role: string; name: string}[]}>('/auth/demo-accounts')});
  const mutation = useMutation({mutationFn: async (role: string) => {
    await finishPendingLogout();
    return post<Identity>('/auth/demo-login', {role});
  }, onSuccess: identity => {setOpen(false); onSuccess(identity);}});
  const ordered = [...(query.data?.accounts || [])].sort((a, b) => Object.keys(descriptions).indexOf(a.role) - Object.keys(descriptions).indexOf(b.role));
  return <div className="demo-entry"><button type="button" className="button secondary full" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen(value => !value)}><Users size={18} />Demo accounts<ChevronDown size={16} className={open ? 'demo-chevron expanded' : 'demo-chevron'} /></button><p>Direct demo login — no email or password needed.</p>
    {open && <section className="demo-inline-panel" id={panelId} aria-label="Demo account options">
      <h2>Choose a demo account</h2><p className="muted">Select any role to sign in directly to its synthetic workspace.</p>
      <ErrorBox error={query.error} retry={() => query.refetch()} /><ErrorBox error={mutation.error} />
      {query.isPending ? <Loading /> : query.data?.enabled && ordered.length ? <div className="demo-role-grid">{ordered.map(account => <button type="button" className="demo-role" key={account.role} disabled={mutation.isPending} onClick={() => mutation.mutate(account.role)} aria-label={`Try ${label(account.role)} demo`} title={descriptions[account.role]}><strong>{label(account.role)}</strong><ArrowRight size={16} /></button>)}</div> : !query.error && <div className="notice">Demo access is not available right now. Please try again later.</div>}
      {mutation.isPending && <p className="demo-signing-in" role="status">Signing in as {label(mutation.variables)}…</p>}
      <p className="demo-admin-note">System administrators use their existing sign-in credentials.</p>
    </section>}
  </div>;
}
