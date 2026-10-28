import { useContext, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Link2, RefreshCw } from 'lucide-react';
import { Auth, Badge, ErrorBox, Field, FormError, Modal, useSave } from '../components/ui';
import { api, date, post, type Case, type Page, type Pair } from '../lib/api';

function clusters(pairs: Pair[]) {
  const groups: Pair[][] = [];
  for (const pair of pairs) {
    const matching = groups.filter(g => g.some(p => [p.a.id, p.b.id].some(id => id === pair.a.id || id === pair.b.id)));
    const joined = [pair, ...matching.flat()];
    for (const group of matching) groups.splice(groups.indexOf(group), 1);
    groups.push(joined);
  }
  return groups;
}

export function CoordinationNotice({ c }: { c: Case }) {
  return <>{c.coordination && <section className="notice coordination-notice"><Link2 size={20} /><div><strong>Coordination group #{c.coordination.id}</strong><p>Linked for coordinated handling. Each complaint retains its own evidence, deadline, decision and appeal.</p><div className="overlap-links">{c.coordination.members.map(m => <Link key={m.id} to={`/complaints/${m.id}`}>{m.reference}{m.id === c.coordination?.primary_complaint_id ? ' (primary)' : ''}</Link>)}</div></div></section>}
    {!!c.recurrences?.length && <section className="card intake-card"><h2>Repeat issue: earlier resolution timeline</h2><p>A similar issue at this institution and incident location was resolved earlier. This new complaint remains separate.</p>{c.recurrences.map(r => <ol className="complaint-timeline" key={r.id}><li><strong>Earlier complaint received</strong><p><Link to={`/complaints/${r.previous_case_id}`}>{r.reference}</Link></p><time dateTime={r.previous_received_at}>{date(r.previous_received_at, true)} IST</time></li><li><strong>Earlier complaint resolved</strong><p><time dateTime={r.resolved_at}>{date(r.resolved_at, true)} IST</time></p></li><li><strong>New complaint received</strong><p>{c.reference}</p><time dateTime={r.new_received_at}>{date(r.new_received_at, true)} IST</time></li></ol>)}</section>}
  </>;
}

export default function OverlapInbox({ compact = false }: { compact?: boolean }) {
  const { user } = useContext(Auth);
  const client = useQueryClient();
  const enabled = !!user.capabilities.overlaps;
  const checked = useRef(false);
  const [notice, setNotice] = useState('');
  const [confirmation, setConfirmation] = useState<{ action: 'merge' | 'reject'; pairs: Pair[] } | null>(null);
  const query = useQuery({ queryKey: ['/overlaps?state=pending&limit=100'], queryFn: ({ signal }) => api<Page<Pair>>('/overlaps?state=pending&limit=100', { signal }), enabled, refetchInterval: 15000 });
  const scan = useMutation({ mutationFn: () => post<{ checked: number }>('/overlaps/scan', {}), onSuccess: async result => { setNotice(`Checked ${result.checked} active complaints. Same issue and same incident location are required. Semantic matching continues separately.`); await client.invalidateQueries(); } });
  useEffect(() => { if (enabled && !checked.current) { checked.current = true; scan.mutate(); } }, [enabled]);
  const save = useSave((values: Record<string, unknown>) => post('/overlaps/bulk', { ...values, action: confirmation?.action, pairs: confirmation?.pairs.map(p => ({ id: p.id, version: p.version })) }), () => setConfirmation(null));
  if (!enabled) return null;
  const pending = query.data?.items.filter(p => !p.stale) || [];
  const groups = clusters(pending.filter(p => p.can_review));
  const preview = confirmation ? [...new Map(confirmation.pairs.flatMap(p => [p.a, p.b]).map(c => [c.id, c])).values()] : [];
  return <section className="card overlap-inbox" aria-label="Overlap alerts and actions">
    <div className="card-heading"><h2><AlertTriangle size={20} /> Overlap alerts {pending.length > 0 && <span className="count">{pending.length}</span>}</h2><button className="button secondary small" disabled={scan.isPending} onClick={() => scan.mutate()}><RefreshCw size={15} />{scan.isPending ? 'Checking…' : 'Check overlaps now'}</button></div>
    <div className="overlap-body"><p>Same issue + same incident location. Shared location alone, or similar complaints at different locations, do not qualify.</p><ErrorBox error={query.error || scan.error} />{notice && <p className="muted" role="status">{notice}</p>}
    {query.data && !pending.length && <p className="muted">No current overlap suggestions in your scope. Older complaints need an incident location before they can be checked.</p>}
    {compact ? pending.length > 0 && <Link className="text-button" to="/overlaps">Review possible overlaps and take action →</Link> : <>
      {groups.map(group => {
        const cases = [...new Map(group.flatMap(p => [p.a, p.b]).map(c => [c.id, c])).values()];
        return <article className="overlap-group" key={group.map(p => p.id).join('-')}><h3>{cases.length} complaints need an overlap decision</h3><p><strong>Incident location:</strong> {cases[0].incident_location}</p><ul>{cases.map(c => <li key={c.id}><Link to={`/complaints/${c.id}`}>{c.reference}</Link><span>{c.category} · {c.owner}</span></li>)}</ul><details><summary>Compare suggested relationships ({group.length})</summary>{group.map(p => <p key={p.id}><Badge value={p.evidence.method === 'text_similarity' ? 'text similarity' : p.band} /> <Link to={`/overlaps/${p.id}`}>Compare {p.a.reference} with {p.b.reference}</Link></p>)}</details><div className="overlap-buttons"><button className="button secondary" onClick={() => { save.reset(); setConfirmation({ action: 'reject', pairs: group }); }}>Reject all</button><button className="button primary" onClick={() => { save.reset(); setConfirmation({ action: 'merge', pairs: group }); }}>Merge all</button></div><small>Actions apply to this group of {group.length} suggestions. Reject dismisses suggestions. Merge links records for coordination.</small></article>;
      })}
      {pending.some(p => !p.can_review) && <p className="muted">Some suggestions require an officer responsible for both cases or an authorized reviewer. Open the pair for details.</p>}
      {query.data?.nextCursor && <Link to="/overlaps" className="text-button">More suggestions are available in the paginated queue.</Link>}
    </>}
    </div>
    <Modal title={confirmation?.action === 'merge' ? 'Merge overlapping complaints' : 'Reject overlap suggestions'} description="Review the records below and record your reason before confirming." open={!!confirmation} onOpenChange={open => { if (!open && !save.isPending) setConfirmation(null); }}>
      <form className="form-grid" onSubmit={event => { event.preventDefault(); const values = Object.fromEntries(new FormData(event.currentTarget)); save.mutate({ reason: values.reason, ...(confirmation?.action === 'merge' ? { primary_complaint_id: Number(values.primary_complaint_id) } : {}) }); }}>
        <p>{confirmation?.action === 'merge' ? 'Create one coordination group. This retains every original complaint and does not close cases, change access, copy evidence, reset deadlines or bypass investigation.' : 'Mark these overlap suggestions unrelated. No complaint will be rejected, closed or deleted.'}</p>
        <ul className="overlap-preview">{preview.map(c => <li key={c.id}><strong>{c.reference}</strong><p>{c.category} · {c.incident_location}</p><p>{c.description || c.issue_summary}</p></li>)}</ul>
        {confirmation?.action === 'merge' && <Field title="Primary complaint"><select name="primary_complaint_id" required>{preview.map(c => <option key={c.id} value={c.id}>{c.reference}</option>)}</select></Field>}
        <Field title="Decision reason"><textarea name="reason" minLength={5} maxLength={2000} rows={3} required /></Field><FormError mutation={save} /><button className="button primary" disabled={save.isPending}>{save.isPending ? 'Saving…' : confirmation?.action === 'merge' ? 'Confirm merge all' : 'Confirm reject all'}</button>
      </form>
    </Modal>
  </section>;
}
