import { Link } from 'react-router-dom';
import { useState, type ReactNode } from 'react';
import { date, label, type Case, type Event, type Page } from '../lib/api';
import { Badge, ErrorBox, Heading, Loading, useData } from '../components/ui';
import HandlingWorkflow from './ComplaintJourney';

export function ClosureReports({ c }: { c: Case }) {
  return c.reports?.length ? <section className="card intake-card"><h2>Closure reports</h2><p className="muted">Watermarked PDF snapshots, preserved separately for each closure.</p>{c.reports.map(r => <p key={r.id}><a className="button secondary" href={`/api/complaints/${c.id}/reports/${r.id}.pdf`}>Download closure PDF - {date(r.created_at, true)} IST</a></p>)}</section> : null;
}

export function ComplaintTimeline({ id }: { id: number }) {
  const [cursor, setCursor] = useState<string | null>(null);
  const query = useData<Page<Event>>(`/complaints/${id}/actions?limit=50${cursor ? '&cursor=' + cursor : ''}`);
  return <section className="card intake-card"><h2>Complaint action timeline</h2><p className="muted">Who acted, what happened, supporting proof and exact time. Latest actions appear first.</p><ErrorBox error={query.error} retry={() => query.refetch()} />{query.isPending ? <Loading /> : <>
    <ol className="complaint-timeline">{query.data?.items.map(e => <li key={e.id}><strong>{e.summary}</strong><p>{e.actor} {e.actor_id ? `(account #${e.actor_id})` : '(system)'}</p><time dateTime={e.created_at}>{date(e.created_at, true)} IST</time><small className="cell-secondary">{e.created_at} UTC</small><p className="description-text">{e.reason || label(e.kind)}</p>{e.proof?.map(p => <p key={p.id}>Proof #{p.id}: {p.filename} - {(p.available ?? p.scan_state === 'clean') ? <a href={`/api/attachments/${p.id}/download`}>Download</a> : label(p.scan_state)}</p>)}{Object.keys(e.changes).length > 0 && <details><summary>Recorded details</summary><pre>{JSON.stringify(e.changes, null, 2)}</pre></details>}</li>)}</ol>
    <div className="button-row">{cursor && <button className="button secondary" onClick={() => setCursor(null)}>Latest actions</button>}{query.data?.nextCursor && <button className="button secondary" onClick={() => setCursor(String(query.data?.nextCursor))}>Older actions</button>}</div></>}</section>;
}

export default function ComplaintRecord({ c, evidence }: { c: Case; evidence: ReactNode }) {
  return <><Link className="back-link" to="/account">Back to my dashboard</Link><Heading eyebrow={c.is_submitter === false ? "APPOINTED COMPLAINT REVIEW" : "YOUR COMPLAINT"} title={c.reference} description={c.institution.name} /><Badge value={c.status} /><section className="card intake-card"><h2>{c.issue_summary || c.category}</h2><p className="description-text">{c.description}</p><dl className="detail-grid"><div><dt>Action taker</dt><dd>{c.owner}</dd></div><div><dt>Registered</dt><dd>{date(c.received_at, true)} IST</dd></div><div><dt>Next action</dt><dd>{c.next_action}</dd></div><div><dt>Category / source</dt><dd>{c.category} / {c.source_channel}</dd></div></dl></section><HandlingWorkflow c={c} /><ClosureReports c={c} /><ComplaintTimeline id={c.id} /><section className="card intake-card">{evidence}</section></>;
}
