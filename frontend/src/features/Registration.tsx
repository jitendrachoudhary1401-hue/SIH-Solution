import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { ArrowRight, CheckCheck, Eye, EyeOff, ShieldCheck } from 'lucide-react';
import { post } from '../lib/api';
import { Field, FormError } from '../components/ui';

const otherTypes = [['faculty', 'Faculty'], ['staff', 'Institution staff'], ['other', 'Other user'], ['officer', 'Bureau officer'], ['lead', 'Bureau lead'], ['reviewer', 'Overlap reviewer'], ['committee', 'Committee member'], ['verifier', 'Independent verifier'], ['executive', 'Executive'], ['auditor', 'Auditor']];
const staffTypes = new Set(['officer', 'lead', 'reviewer', 'committee', 'verifier', 'executive', 'auditor']);

export default function Registration({ audience }: { audience: 'family' | 'other' }) {
  const [accountType, setAccountType] = useState(audience === 'family' ? 'student' : 'faculty');
  const [show, setShow] = useState(false);
  const [validation, setValidation] = useState('');
  const mutation = useMutation({ mutationFn: (values: Record<string, FormDataEntryValue>) => post<{ message: string; approval_pending: boolean }>('/auth/register', values) });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    if (values.password !== values.confirm_password) { setValidation('Passwords do not match.'); return; }
    setValidation(''); mutation.mutate(values);
  }
  return <div className="registration-page">
    <aside className="registration-story">
      <Link to="/officer/login" className="brand"><img className="brand-logo" src="/onecase-logo.png" alt="OneCase" /><span>OneCase<small>Institution complaint coordination</small></span></Link>
      <div><p className="eyebrow">YOUR NEXT STEP STARTS HERE</p><h2>A voice.<br />A clear record.<br />A way forward.</h2><p>Create your account to keep track of the records shared with you, in one place.</p>
      <ol><li><span>01</span><div><strong>Choose your account</strong><p>Register as a student, parent or another member of the community.</p></div></li><li><span>02</span><div><strong>Make it yours</strong><p>Use your own email and a private passphrase.</p></div></li><li><span>03</span><div><strong>Start fresh</strong><p>Your workspace starts empty. Activity appears as real records are added or shared.</p></div></li></ol></div>
      <p className="registration-trust"><ShieldCheck size={18} /> Private access. Clear accountability.</p>
    </aside>
    <main className="registration-main">
      <p className="registration-signin">Already have an account? <Link to="/officer/login">Sign in <ArrowRight size={14} /></Link></p>
      <section className="registration-card">
        <p className="eyebrow">CREATE YOUR ONECASE ACCOUNT</p>
        <h1>{audience === 'family' ? 'Student & parent registration' : 'Other user registration'}</h1>
        <p className="muted">{audience === 'family' ? 'A personal workspace for students and parents.' : 'For faculty, institution staff and authorized coordination teams.'}</p>
        <nav className="registration-tabs" aria-label="Registration category"><Link className={audience === 'family' ? 'selected' : ''} to="/register/student-parent">Student / Parent</Link><Link className={audience === 'other' ? 'selected' : ''} to="/register/other">Other users</Link></nav>
        {mutation.isSuccess ? <div className="registration-success" role="status"><CheckCheck size={34} /><h2>Account created</h2><p>{mutation.data.message}</p><p>Your workspace starts with zero cases and alerts.</p><Link className="button primary full" to="/officer/login">Continue to sign in <ArrowRight size={17} /></Link></div> : <form onSubmit={submit} className="registration-form">
          <Field title="Account type"><select name="account_type" value={accountType} onChange={event => setAccountType(event.target.value)} required>{(audience === 'family' ? [['student', 'Student'], ['parent', 'Parent / Guardian']] : otherTypes).map(([value, title]) => <option key={value} value={value}>{title}</option>)}</select></Field>
          <Field title="Full name"><input name="name" autoComplete="name" placeholder="Your full name" minLength={2} maxLength={120} required /></Field>
          <Field title="Email address"><input name="email" type="email" autoComplete="email" placeholder="you@example.com" maxLength={180} required /></Field>
          <Field title={staffTypes.has(accountType) ? 'Organization' : 'Institution (optional)'}><input name="organization" autoComplete="organization" placeholder="Institution or organization name" maxLength={200} minLength={staffTypes.has(accountType) ? 2 : undefined} required={staffTypes.has(accountType)} /></Field>
          <Field title="Password" hint="Use at least 12 characters."><div className="password-input"><input name="password" type={show ? 'text' : 'password'} autoComplete="new-password" minLength={12} maxLength={1024} required /><button type="button" aria-label={show ? 'Hide password' : 'Show password'} onClick={() => setShow(!show)}>{show ? <EyeOff size={18} /> : <Eye size={18} />}</button></div></Field>
          <Field title="Confirm password"><input name="confirm_password" type={show ? 'text' : 'password'} autoComplete="new-password" minLength={12} maxLength={1024} required /></Field>
          {staffTypes.has(accountType) && <div className="notice">This creates an access request. An administrator must approve your role and scope before you can access staff records.</div>}
          {validation && <p className="error" role="alert">{validation}</p>}<FormError mutation={mutation} />
          <button className="button primary full" disabled={mutation.isPending}>{mutation.isPending ? 'Creating account…' : 'Create account'}<ArrowRight size={17} /></button>
        </form>}
      </section><p className="registration-footer">One workspace. Clear ownership. Accountable action.</p>
    </main>
  </div>;
}
