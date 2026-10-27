import { useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { api, post, type Case, type Institution, type User } from '../lib/api';
import { ErrorBox, Field, Loading, useData } from '../components/ui';

type Options = { institutions: Institution[]; categories: string[]; channels: string[]; max_upload_bytes: number; max_files: number };
type Upload = { file: File; key: string; done: boolean };
export default function ComplaintIntake({ user }: { user: User }) {
  const options = useData<Options>('/intake/options');
  const [institution, setInstitution] = useState('');
  const [channel, setChannel] = useState('OneCase portal');
  const [files, setFiles] = useState<Upload[]>([]);
  const [receipt, setReceipt] = useState<Case | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const key = useRef(crypto.randomUUID());
  const client = useQueryClient();
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); setError(null); setBusy(true);
    try {
      let current = receipt;
      if (!current) {
        const values = Object.fromEntries(new FormData(e.currentTarget));
        current = await post<Case>('/intake/complaints', {
          ...values, institution_id: institution ? Number(institution) : null,
          declaration: values.declaration === 'on',
        }, 'POST', { 'Idempotency-Key': key.current });
        setReceipt(current);
      }
      for (const upload of files) {
        if (upload.done) continue;
        const fresh = await api<Case>(`/complaints/${current.id}`);
        const form = new FormData(); form.set('file', upload.file); form.set('version', String(fresh.version)); form.set('upload_key', upload.key);
        await api(`/complaints/${current.id}/attachments`, { method: 'POST', body: form });
        upload.done = true;
        setFiles([...files]);
      }
      await client.invalidateQueries();
    } catch (cause) { setError(cause as Error); }
    finally { setBusy(false); }
  }
  if (options.isPending) return <Loading />;
  if (!options.data) return <ErrorBox error={options.error} retry={() => options.refetch()} />;
  const data = options.data;
  function choose(selected: FileList | null) {
    const next = Array.from(selected || []);
    if (next.length > data.max_files || next.some(f => f.size > data.max_upload_bytes || !/\.(pdf|png|jpe?g|mp4|webm)$/i.test(f.name))) {
      setError(new Error(`Choose up to ${data.max_files} PDF, PNG, JPEG, MP4 or WebM files, each at most ${(data.max_upload_bytes / 1048576).toFixed(0)} MB.`)); return;
    }
    setError(null); setFiles(next.map(file => ({ file, key: crypto.randomUUID(), done: false })));
  }
  return <section className="card intake-card" id="register-complaint"><h2>Register a complaint</h2><p className="muted">For enrolled students, parents, faculty, non-teaching staff and other stakeholders. Your complaint receives a unique reference and is shared with the responsible action taker and system administrator.</p>
    {receipt && <div className="notice" role="status"><div><strong>Complaint registered: {receipt.reference}</strong><p>{files.some(f => !f.done) ? 'Your complaint is saved. Retry any unfinished proof uploads below.' : 'Your complaint and selected uploads are saved. Check each file’s validation and malware scan status in the complaint record.'}</p><Link className="button primary" to={`/complaints/${receipt.id}`}>View complaint and action timeline</Link></div></div>}
    <form className="form-grid" onSubmit={submit}>
      <fieldset disabled={busy || !!receipt} className="intake-fields">
        <Field title="Institution" hint="Search the institution directory, or enter an unlisted institution. Unlisted details require verification."><select value={institution} onChange={e => setInstitution(e.target.value)} required={user.is_demo}><option value="">Enter institution details below</option>{data.institutions.map(i => <option key={i.id} value={i.id}>{i.name} - {i.region}</option>)}</select></Field>
        {!institution && <div className="form-row"><Field title="Institution name"><input name="institution_name" required minLength={3} maxLength={200} /></Field><Field title="State / region"><input name="region" required minLength={2} maxLength={80} /></Field></div>}
        <Field title="Complaint category"><select name="category" required>{data.categories.map(c => <option key={c}>{c}</option>)}</select></Field>
        <Field title="Complaint summary"><input name="issue_summary" required minLength={5} maxLength={300} /></Field>
        <Field title="What happened?" hint="Describe the issue, relevant dates and the remedy you seek."><textarea name="description" required minLength={20} maxLength={20000} rows={5} /></Field>
        <Field title={user.role === 'parent' ? 'Affected student name' : 'Affected person (optional)'}><input name="affected_person" required={user.role === 'parent'} maxLength={150} /></Field>
        <Field title="Relationship / authority to represent" hint={user.role === 'parent' ? 'Explain your relationship to the student.' : 'Complete this if filing on behalf of someone else.'}><textarea name="representation_basis" required={user.role === 'parent'} minLength={user.role === 'parent' ? 5 : undefined} maxLength={1000} rows={2} /></Field>
        <Field title="Source"><select name="source_channel" value={channel} onChange={e => setChannel(e.target.value)}>{data.channels.map(c => <option key={c}>{c}</option>)}</select></Field>
        {channel !== 'OneCase portal' && <Field title="Existing portal reference" hint="Enter the reference already issued by that portal. This records the source; it does not submit to the external portal."><input name="source_reference" required maxLength={150} /></Field>}
        <Field title="Photos, videos and documents as proof" hint={`PDF, JPG, PNG, MP4 or WebM. Up to ${data.max_files} files, ${(data.max_upload_bytes / 1048576).toFixed(0)} MB each. Videos up to 5 minutes and 1080p. Files are private and scanned before download.`}><input type="file" accept=".pdf,.png,.jpg,.jpeg,.mp4,.webm" multiple onChange={e => choose(e.target.files)} /></Field>
        <label className="checkbox-field"><input type="checkbox" name="declaration" required /> I confirm these details are accurate to the best of my knowledge and I am authorized to submit this complaint.</label>
      </fieldset>
      {!!files.length && <ul className="proof-status">{files.map(f => <li key={f.key}>{f.file.name}: {f.done ? 'Uploaded - awaiting scan' : 'Awaiting upload'}</li>)}</ul>}
      <ErrorBox error={error} />
      {(!receipt || files.some(f => !f.done)) && <button className="button primary" disabled={busy}>{busy ? 'Saving complaint and proof...' : receipt ? 'Retry unfinished uploads' : 'Register complaint'}</button>}
    </form>
  </section>;
}
