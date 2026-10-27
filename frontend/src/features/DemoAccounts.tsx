import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { ArrowRight, Users } from 'lucide-react';
import { api, post, finishPendingLogout, label, type User } from '../lib/api';
import { Modal, Loading, ErrorBox } from '../components/ui';

type Identity = {user: User; csrf: string};
const descriptions: Record<string, string> = {
  student: 'A personal student workspace', parent: 'Follow records shared with a parent', faculty: 'A faculty member’s personal workspace',
  staff: 'An institution staff workspace', other: 'A community member’s workspace', officer: 'Receive and coordinate demo cases',
  lead: 'Manage a demonstration bureau', reviewer: 'Review potential case relationships', committee: 'Access appointed proceedings',
  verifier: 'Review compliance evidence', executive: 'Explore scoped monitoring', auditor: 'View scoped records and reports',
};

export default function DemoAccounts({onSuccess}: {onSuccess: (identity: Identity) => void}) {
  const [open, setOpen] = useState(false);
  const query = useQuery({queryKey: ['demo-accounts'], enabled: open, retry: false,
    queryFn: () => api<{enabled: boolean; accounts: {role: string; name: string}[]}>('/auth/demo-accounts')});
  const mutation = useMutation({mutationFn: async (role: string) => {
    await finishPendingLogout();
    return post<Identity>('/auth/demo-login', {role});
  }, onSuccess: identity => {setOpen(false); onSuccess(identity);}});
  return <div className="demo-entry"><button type="button" className="button secondary full" onClick={() => setOpen(true)}><Users size={18} />Demo accounts</button><p>Explore OneCase with a demonstration account.</p>
    <Modal title="Choose a demo account" description="Select a role to enter its demonstration workspace. All activity is limited to synthetic records." open={open} onOpenChange={setOpen}>
      <ErrorBox error={query.error} retry={() => query.refetch()} /><ErrorBox error={mutation.error} />
      {query.isPending ? <Loading /> : query.data?.enabled && query.data.accounts.length ? <div className="demo-role-grid">{query.data.accounts.map(account => <button className="demo-role" key={account.role} disabled={mutation.isPending} onClick={() => mutation.mutate(account.role)} aria-label={`Try ${label(account.role)} demo`}><span><strong>{label(account.role)}</strong><small>{descriptions[account.role]}</small></span><ArrowRight size={18} /></button>)}</div> : !query.error && <div className="notice">Demo access is not available right now. Please try again later.</div>}
      <p className="demo-admin-note">System administrators use their existing sign-in credentials.</p>
    </Modal>
  </div>;
}
