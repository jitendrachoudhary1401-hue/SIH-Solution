import { useContext, type FormEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, post, date, label, type Case } from '../lib/api';
import { Auth, ErrorBox, Field, FormError, Loading, useSave } from '../components/ui';

const stages = [
  ['initial_review', 'Faculty / grievance review', 'An appointed reviewer records a recommendation. Every complaint continues to the officer, including disputed or reportedly resolved cases.'],
  ['officer_triage', 'Officer review and triage', 'The officer checks the complaint and appoints the specialized handling team.'],
  ['committee_review', 'Lead and committee', 'The lead and committee each record their assessment before investigation.'],
  ['investigation', 'Investigate and verify', 'Reviewer and verifier examine the facts. An auditor joins financial or infrastructure cases.'],
  ['executive_decision', 'Executive decision', 'The executive reviews the reports and records an outcome supported by evidence.'],
  ['resolved', 'Outcome and appeal', 'The complainant views the decision and closure PDF, or requests an appeal review.'],
];
const stepRoles: Record<string,string[]> = {initial_review:['faculty_reviewer'],officer_triage:['officer'],
  committee_review:['lead','committee'],investigation:['reviewer','verifier'],executive_decision:['executive'],resolved:['executive']};

export function LoginJourney() {
  return <section className="login-workflow" aria-labelledby="public-workflow-title">
    <p className="eyebrow">HOW YOUR COMPLAINT MOVES</p><h2 id="public-workflow-title">One complaint. A traceable path.</h2>
    <p className="journey-intro">Students, parents, faculty, institution staff and other stakeholders register a complaint with supporting evidence. Every handover follows the same recorded journey, starting with an appointed faculty or grievance reviewer.</p>
    <ol className="handling-timeline public-timeline">{stages.map(([key, title, description], i) => <li key={key}><span className="handling-marker" aria-hidden="true">{String(i + 1).padStart(2, '0')}</span><div><h3>{title}</h3><p>{description}</p></div></li>)}</ol>
    <div className="journey-solution"><h3>Where OneCase connects the work</h3><dl>
      <div><dt>One institution record</dt><dd>Authorized teams can follow institution-related complaints across bureaus.</dd></div>
      <div><dt>Clear ownership and handovers</dt><dd>Assigned people, reports, deadlines and actions stay attached to the complaint.</dd></div>
      <div><dt>Overlap and repeat-issue alerts</dt><dd>Similar issues at the same incident location can flag active overlaps. An earlier resolved case appears separately with its resolution timeline. Authorized people decide the relationship.</dd></div>
      <div><dt>Evidence and accountable outcomes</dt><dd>Independent checks, a recorded executive outcome and an appeal request preserve the case history.</dd></div>
    </dl><p className="muted">Overlap checks require a verified institution, the same issue and the same reported incident location. Semantic matching also needs a running worker. External grievance or appeal proceedings keep their own authorities and timelines.</p></div>
  </section>;
}

type Flow = {managed: boolean; stage: string; stage_label: string; cycle: number; version: number; outcome: string | null;
  public_decision: string; auditor_required: boolean; access_until: string; can_manage: boolean; can_report: boolean; can_advance: boolean; can_appeal: boolean;
  missing_reports: string[]; team: {role: string; user_id: number | null; name: string}[];
  reports: {id: number; role: string; actor_id: number; report: string; created_at: string}[];
  report_history: {id: number; cycle: number; stage: string; role: string; report: string; created_at: string}[]};
type Candidate = {id: number; name: string; roles: string[]};

export default function HandlingWorkflow({c}: {c: Case}) {
  const {user} = useContext(Auth);
  const query = useQuery({queryKey:[`/complaints/${c.id}/case-workflow`],
    queryFn:({signal}) => api<Flow>(`/complaints/${c.id}/case-workflow`,{signal})});
  const flow = query.data;
  const choices = useQuery({queryKey: ['handling-team', c.id, flow?.version], enabled: !!flow?.can_manage,
    queryFn: ({signal}) => api<{items: Candidate[]}>(`/complaints/${c.id}/case-workflow/candidates`,{signal})});
  const save = useSave(({action, values}: {action: string; values: Record<string, unknown>}) => post(`/complaints/${c.id}/case-workflow/${action}`, values));
  function submitReport(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const f = new FormData(e.currentTarget);
    const action = (e.nativeEvent as SubmitEvent).submitter?.getAttribute('value') || 'reports';
    save.mutate({action, values: {version: flow?.version, report: f.get('report'), evidence_ids: f.getAll('evidence_ids').map(Number),
      ...(flow?.stage === 'executive_decision' && action === 'advance' ? {outcome: f.get('outcome'), outcome_document_id: Number(f.get('outcome_document_id')) || null,
        communication: f.get('communication'), external_continues: f.get('external_continues') === 'on'} : {})}});
  }
  if (query.isPending) return <Loading />;
  if (query.error) return <ErrorBox error={query.error} retry={() => query.refetch()} />;
  if (!flow?.managed) return <section className="card handling-panel"><h2>Complaint handling timeline</h2><p>This existing case retains its recorded workflow and proceedings.</p>
    {(user.roles.includes('admin') || user.id === c.owner_id || user.roles.includes('lead') && user.bureau_id === c.bureau_id) && <button className="button secondary" disabled={save.isPending} onClick={() => save.mutate({action:'start',values:{version:c.version,report:'Enable the structured internal complaint handling workflow.'}})}>Enable structured handling</button>}<FormError mutation={save}/></section>;
  const current = flow.stage === 'appeal_review' ? 2 : stages.findIndex(s => s[0] === flow.stage);
  const available = c.attachments?.filter(a => a.available ?? a.scan_state === 'clean') || [];
  return <section className="card handling-panel" aria-labelledby="case-handling-title">
    <div className="card-heading"><div><p className="eyebrow">COMPLAINT HANDLING · CYCLE {flow.cycle}</p><h2 id="case-handling-title">{flow.stage_label}</h2></div><span className="badge">{flow.stage === 'resolved' ? flow.outcome === 'not_upheld' ? 'Closed: not upheld' : 'Resolved' : 'In progress'}</span></div>
    <ol className="handling-timeline">{stages.map(([key,title,description],i) => <li key={key} className={i < current || flow.stage === 'resolved' ? 'complete' : i === current ? 'current' : ''} aria-current={i === current ? 'step' : undefined}>
      <span className="handling-marker" aria-hidden="true">{String(i + 1).padStart(2,'0')}</span><div><h3>{flow.stage === 'appeal_review' && key === 'committee_review' ? 'Appeal review' : title}</h3><p>{description}</p><p className="handling-assignees">{flow.team.filter(t => (stepRoles[key] || []).includes(t.role) || key === 'investigation' && flow.auditor_required && t.role === 'auditor').map(t => `${label(t.role)}: ${t.name}`).join(' · ')}</p><small>{i < current || flow.stage === 'resolved' ? 'Completed' : i === current ? 'Current stage' : 'Upcoming'}</small></div></li>)}</ol>
    <p className="muted">Audit review: {flow.auditor_required ? 'Required before the executive decision' : 'Can be added when the case requires it'}. External proceedings remain separate.</p>
    <details className="handling-team"><summary>Assigned handling team</summary><dl className="detail-grid">{flow.team.map(t => <div key={t.role}><dt>{label(t.role)}</dt><dd>{t.name}</dd></div>)}</dl><p className="muted">Case-bound team access until {date(flow.access_until, true)} IST. Access also requires an active approved role and no recorded conflict.</p></details>
    {flow.public_decision && <div className="notice"><div><strong>{flow.stage === 'resolved' ? 'Communicated outcome' : 'Previous communicated outcome'}</strong><p className="description-text">{flow.public_decision}</p></div></div>}
    {flow.can_manage && flow.stage !== 'resolved' && <details className="handling-team"><summary>Appoint or update the handling team</summary><p>Choose approved accounts. Each role requires a different person. Use Transfer case to change the accountable officer.</p><ErrorBox error={choices.error}/><form key={flow.version} onSubmit={e => {
      e.preventDefault(); const f = new FormData(e.currentTarget); const values: Record<string,unknown> = {version:flow.version, reason:f.get('reason'), approval_reference:f.get('approval_reference'),auditor_required:f.get('auditor_required') === 'on'};
      flow.team.filter(t => t.role !== 'officer').forEach(t => {values[t.role + '_id'] = Number(f.get(t.role + '_id')) || null;}); save.mutate({action:'team',values});
    }}><div className="form-row">{flow.team.filter(t => t.role !== 'officer').map(t => <Field title={label(t.role)} key={t.role}><select name={t.role + '_id'} defaultValue={t.user_id || ''}><option value="">Awaiting assignment</option>{choices.data?.items.filter(u => u.roles.includes(t.role)).map(u => <option value={u.id} key={u.id}>{u.name}</option>)}</select></Field>)}</div>
      <label className="check-field"><input type="checkbox" name="auditor_required" defaultChecked={flow.auditor_required}/> Require an auditor report</label>
      <Field title="Appointment approval reference"><input name="approval_reference" minLength={5} maxLength={200} required/></Field><Field title="Appointment reason"><input name="reason" minLength={5} maxLength={1000} required/></Field>
      <p className="muted">If an account is missing, the administrator must approve its staff role first. Faculty complainant accounts do not receive reviewer privileges.</p><button className="button secondary" disabled={save.isPending || !choices.data}>Save handling team</button></form></details>}
    {flow.can_report && <form className="handling-report" onSubmit={submitReport}><h3>Record your stage report</h3>{flow.stage === 'initial_review' && <p className="notice">An initial report cannot close or dismiss a complaint. Record the evidence and forward it to the officer even if you believe it is resolved or false.</p>}<Field title="Stage report / handover reason"><textarea name="report" rows={4} minLength={20} maxLength={10000} required/></Field>
      {available.length > 0 && <fieldset><legend>Supporting evidence</legend>{available.map(a => <label className="check-field" key={a.id}><input type="checkbox" name="evidence_ids" value={a.id}/>{a.filename}</label>)}</fieldset>}
      {flow.stage === 'executive_decision' && <><Field title="Outcome"><select name="outcome"><option value="resolved">Resolved</option><option value="not_upheld">Not upheld</option></select></Field><Field title="Outcome document"><select name="outcome_document_id" required><option value="">Select available evidence</option>{available.map(a => <option key={a.id} value={a.id}>{a.filename}</option>)}</select></Field><Field title="Outcome communication / recipient reference"><textarea name="communication" minLength={10} maxLength={2000} required/></Field><label className="check-field"><input type="checkbox" name="external_continues"/> Linked external proceedings continue after internal closure</label></>}
      {flow.missing_reports.length > 0 && <p className="muted">Required appointments or reports: {flow.missing_reports.map(label).join(', ')}.</p>}
      <div className="button-row"><button className="button secondary" type="submit" value="reports" disabled={save.isPending}>Save stage report</button>{flow.can_advance && <button className="button primary" type="submit" value="advance" disabled={save.isPending}>{flow.stage === 'executive_decision' ? 'Record decision and communicate outcome' : 'Complete stage and hand over'}</button>}</div></form>}
    {flow.can_appeal && <details className="handling-team"><summary>Request an appeal review</summary><p>The request opens a new recorded review cycle. An appeal decision requires a different executive. External filing, eligibility and deadlines must be confirmed with the relevant authority.</p><form onSubmit={e => {e.preventDefault();const f = new FormData(e.currentTarget);save.mutate({action:'appeal',values:{version:flow.version,report:f.get('report')}});}}><Field title="Appeal reason"><textarea name="report" rows={4} minLength={20} maxLength={10000} required/></Field><button className="button primary" disabled={save.isPending}>Submit appeal request</button></form></details>}
    {flow.report_history.length > 0 && <details className="handling-team"><summary>Recorded handling reports</summary>{flow.report_history.map(r => <article key={r.id}><h3>{label(r.role)} · {label(r.stage)} · Cycle {r.cycle}</h3><p className="description-text">{r.report}</p><small>{date(r.created_at,true)} IST</small></article>)}</details>}
    <FormError mutation={save}/>
  </section>;
}
