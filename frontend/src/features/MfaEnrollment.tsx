import { useState, type FormEvent } from 'react';
import { useMutation } from '@tanstack/react-query';
import { ShieldCheck } from 'lucide-react';
import { post, setCsrf } from '../lib/api';
import { ErrorBox, Field } from '../components/ui';

export default function MfaEnrollment({ onComplete, onLogout }: { onComplete: () => void; onLogout: () => void }) {
  const [setup, setSetup] = useState<{ secret: string; uri: string } | null>(null);
  const [codes, setCodes] = useState<string[]>([]);
  const enroll = useMutation({ mutationFn: () => post<{ secret: string; uri: string }>('/auth/mfa/setup', {}), onSuccess: setSetup });
  const confirm = useMutation({ mutationFn: (code: string) => post<{ csrf: string; recovery_codes: string[] }>('/auth/mfa/confirm', { code }),
    onSuccess: result => { setCsrf(result.csrf); setCodes(result.recovery_codes); setSetup(null); } });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); confirm.mutate(String(new FormData(event.currentTarget).get('code')));
  }
  return <main className="enrollment-page"><section className="card security-card">
    <img className="brand-logo" src="/onecase-emblem.png" alt="OneCase" />
    <p className="eyebrow">PROTECT YOUR WORKSPACE</p><h1>Set up your authenticator</h1>
    <p>Your password is verified. Complete authenticator setup before accessing case records or administration. This setup session lasts ten minutes.</p>
    {!setup && !codes.length && <button className="button primary" disabled={enroll.isPending} onClick={() => enroll.mutate()}>Set up authenticator</button>}
    <ErrorBox error={enroll.error} />
    {setup && <><div className="secret-once"><span>Enter this key in your authenticator</span><code>{setup.secret}</code><small>OneCase · 6 digits · 30-second interval</small></div>
      <form onSubmit={submit}><Field title="Authenticator code"><input name="code" inputMode="numeric" autoComplete="one-time-code" minLength={6} maxLength={6} required /></Field>
        <ErrorBox error={confirm.error} /><button className="button primary" disabled={confirm.isPending}>Verify and enable MFA</button></form></>}
    {codes.length > 0 && <div className="recovery-codes"><ShieldCheck size={24} /><strong>Save your one-time recovery codes</strong>
      <p>Store these somewhere safe. They are displayed only once.</p><div>{codes.map(code => <code key={code}>{code}</code>)}</div>
      <button className="button primary" onClick={onComplete}>I saved my codes — continue</button></div>}
    <button className="text-button" onClick={onLogout}>Sign out</button>
  </section></main>;
}
