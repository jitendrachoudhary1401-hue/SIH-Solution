import { useState, type FormEvent } from 'react';
import { post, type Institution } from '../lib/api';
import { useData, useSave, Field, Modal, ErrorBox, Loading } from '../components/ui';

export default function InstitutionVerification() {
  const query = useData<{ items: Institution[] }>('/admin/institutions');
  const [selected, setSelected] = useState<Institution | null>(null);
  const save = useSave((values: Record<string, unknown>) => post(`/admin/institutions/${selected?.id}/verify`, values), () => setSelected(null));
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); save.mutate(Object.fromEntries(new FormData(event.currentTarget))); }
  return <section className="card security-card"><h2>Institution identity review</h2>
    <p>Confirm the institution against an authorized source before semantic matching. Similar names never merge records automatically.</p>
    <ErrorBox error={query.error} />{query.isPending ? <Loading /> : query.data?.items.length ? query.data.items.map(item =>
      <div className="section-toolbar" key={item.id}><div><strong>{item.name}</strong><p>{item.region} · Institution #{item.id}</p></div>
        <button className="button secondary small" onClick={() => { save.reset(); setSelected(item); }}>Review identity</button></div>) : <p>No institutions await identity review.</p>}
    <Modal title="Verify institution identity" description="Record the exact identifier and the source of competent verification. Leading zeros are preserved." open={!!selected} onOpenChange={open => !open && setSelected(null)}>
      <form className="form-grid" onSubmit={submit}><strong>{selected?.name}</strong>
        <Field title="Verified institution identifier"><input name="external_id" defaultValue={selected?.external_id || ''} maxLength={60} required /></Field>
        <Field title="Approval / source reference"><input name="approval_reference" minLength={5} maxLength={200} required /></Field>
        <Field title="Verification reason"><textarea name="reason" minLength={5} maxLength={1000} required /></Field>
        <ErrorBox error={save.error} /><button className="button primary" disabled={save.isPending}>Confirm verified identity</button>
      </form>
    </Modal>
  </section>;
}
