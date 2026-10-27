import { useEffect, useState, type FormEvent } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, ArrowRight, CheckCheck, Eye, EyeOff, KeyRound, Mail } from 'lucide-react';
import { ApiError, post, setCsrf } from '../lib/api';
import { Field, FormError } from '../components/ui';

export default function PasswordRecovery() {
  const location = useLocation();
  const reset = location.pathname === '/reset-password';
  const [token] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get('token') || '');
  const [show, setShow] = useState(false);
  const [mfa, setMfa] = useState(false);
  const [validation, setValidation] = useState('');
  const client = useQueryClient();
  useEffect(() => {
    if (reset && window.location.hash) window.history.replaceState(null, '', location.pathname);
  }, [reset, location.pathname]);
  const mutation = useMutation({
    mutationFn: (values: Record<string, FormDataEntryValue>) => post<{message: string}>(reset ? '/auth/reset-password' : '/auth/forgot-password', reset ? {...values, token} : values),
    onSuccess: async () => {
      if (reset) { setCsrf(''); await client.cancelQueries(); client.clear(); }
    },
    onError: error => { if (error instanceof ApiError && error.mfaRequired) setMfa(true); },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    if (reset && values.password !== values.confirm_password) { setValidation('Passwords do not match.'); return; }
    setValidation(''); mutation.mutate(values);
  }
  return <main className="recovery-page"><Link className="brand recovery-brand" to="/officer/login"><img className="brand-logo" src="/onecase-logo.png" alt="OneCase" /><span>OneCase<small>Institution complaint coordination</small></span></Link><section className="card recovery-card">
    <span className="recovery-icon">{reset ? <KeyRound size={25} /> : <Mail size={25} />}</span>
    <p className="eyebrow">ACCOUNT RECOVERY</p>
    <h1>{mutation.isSuccess ? reset ? 'Password updated' : 'Check your email' : reset ? 'Set a new password' : 'Forgot your password?'}</h1>
    {mutation.isSuccess ? <div className="recovery-success" role="status"><CheckCheck size={28} /><p>{mutation.data.message}</p>{!reset && <p className="muted">Check your spam folder too. The link expires in 20 minutes.</p>}<Link className="button primary full" to="/officer/login">Back to sign in <ArrowRight size={17} /></Link></div> : reset && !token ? <><div className="notice">Open the complete reset link from your email. If it has expired, request a new link.</div><Link className="button primary full" to="/forgot-password">Request a reset link</Link></> : <>
      <p className="muted">{reset ? 'Choose a new password with at least 12 characters.' : 'Enter your account email. We will send you a private link to reset your password.'}</p>
      <form className="registration-form" onSubmit={submit}>
        {reset ? <><Field title="New password"><div className="password-input"><input name="password" type={show ? 'text' : 'password'} autoComplete="new-password" required minLength={12} maxLength={1024} /><button type="button" aria-label={show ? 'Hide password' : 'Show password'} onClick={() => setShow(!show)}>{show ? <EyeOff size={18} /> : <Eye size={18} />}</button></div></Field><Field title="Confirm new password"><input name="confirm_password" type={show ? 'text' : 'password'} autoComplete="new-password" required minLength={12} maxLength={1024} /></Field>{mfa && <Field title="Authenticator or recovery code"><input name="verification_code" autoComplete="one-time-code" maxLength={100} required /></Field>}</> : <Field title="Email address"><input name="email" type="email" autoComplete="email" placeholder="you@example.com" required maxLength={180} /></Field>}
        {validation && <p className="error" role="alert">{validation}</p>}<FormError mutation={mutation} />
        <button className="button primary full" disabled={mutation.isPending}>{mutation.isPending ? 'Please wait…' : reset ? 'Update password' : 'Send reset link'}<ArrowRight size={17} /></button>
      </form></>}
    <Link className="recovery-back" to="/officer/login"><ArrowLeft size={15} /> Back to sign in</Link>
  </section></main>;
}
