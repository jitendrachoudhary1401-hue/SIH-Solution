import { createContext, useContext, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { Link, NavLink, Navigate, Outlet, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as Dialog from '@radix-ui/react-dialog';
import { Activity, ArrowDownToLine, ArrowLeft, ArrowRight, Bell, Building2, Check, CheckCheck, ChevronDown, ChevronLeft, ChevronRight, CircleHelp, Clock3, FileCheck2, FileText, FolderOpen, LayoutDashboard, Link2, LogOut, Menu, Moon, Plus, Search, ShieldCheck, Sun, Upload, X, Eye, EyeOff, AlertCircle, RefreshCw, SlidersHorizontal, GraduationCap, Briefcase, UserCheck } from 'lucide-react';
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api, post, setCsrf, date, label, ApiError, type Case, type Directory, type Event, type Institution, type Page, type Pair, type Summary, type User, type AccountRequest } from './lib/api';

const Auth = createContext<{ user: User; logout: () => void }>(null!);
const Toast = createContext<(message: string) => void>(() => {});
const useData = <T,>(path: string) => useQuery({ queryKey: [path], queryFn: () => api<T>(path) });

function ErrorBox({ error, retry }: { error: Error | null; retry?: () => void }) {
  return error ? <div className="error" role="alert"><AlertCircle size={18} /><span>{error.message}</span>{retry && <button className="text-button" onClick={retry}>Retry</button>}</div> : null;
}
function Loading() { return <div className="loading" role="status"><RefreshCw className="spin" size={20} /> Loading workspace…</div>; }
function Empty({ title = 'No records to show', children }: { title?: string; children?: ReactNode }) { return <div className="empty"><FolderOpen size={32} /><h3>{title}</h3><p>{children || 'Records in your authorized scope will appear here.'}</p></div>; }
function Badge({ value, tone }: { value: string; tone?: string }) { return <span className={`badge ${tone || value}`}>{label(value)}</span>; }
function Modal({ title, description, trigger, children, open, onOpenChange }: { title: string; description: string; trigger?: ReactNode; children: ReactNode; open?: boolean; onOpenChange?: (open: boolean) => void }) {
  return <Dialog.Root open={open} onOpenChange={onOpenChange}>{trigger && <Dialog.Trigger asChild>{trigger}</Dialog.Trigger>}<Dialog.Portal><Dialog.Overlay className="overlay" /><Dialog.Content className="dialog"><div className="dialog-heading"><div><Dialog.Title>{title}</Dialog.Title><Dialog.Description>{description}</Dialog.Description></div><Dialog.Close className="icon-button" aria-label="Close dialog"><X size={20} /></Dialog.Close></div>{children}</Dialog.Content></Dialog.Portal></Dialog.Root>;
}
function useSave<T>(fn: (data: T) => Promise<unknown>, onSuccess?: () => void) {
  const client = useQueryClient(); const toast = useContext(Toast);
  return useMutation({ mutationFn: fn, onSuccess: async () => { await client.invalidateQueries(); toast('Changes saved successfully'); onSuccess?.(); } });
}
function Heading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="muted">{description}</p></div>{action}</div>;
}
function FormError({ mutation }: { mutation: { error: Error | null } }) { return <ErrorBox error={mutation.error} />; }
function Field({ title, children, hint }: { title: string; children: ReactNode; hint?: string }) { return <label className="field"><span>{title}</span>{children}{hint && <small>{hint}</small>}</label>; }
function Pager({ page, setCursor, cursor }: { page: Page<unknown>; cursor: string | null; setCursor: (value: string | null) => void }) {
  return <div className="pager"><span>{page.total} authorized records · Updated {date(page.asOf, true)} IST</span><div>{cursor && <button className="button secondary small" onClick={() => setCursor(null)}><ChevronLeft size={14} /> First page</button>}<button className="button secondary small" disabled={!page.nextCursor} onClick={() => setCursor(String(page.nextCursor))}>Next page <ChevronRight size={14} /></button></div></div>;
}

export default function App() {
  const client = useQueryClient(); const [message, setMessage] = useState('');
  const [expired, setExpired] = useState(false);
  const identity = useQuery({ queryKey: ['identity'], queryFn: () => api<{ user: User; csrf: string }>('/auth/me'), retry: false, staleTime: 5 * 60000 });
  useEffect(() => { if (identity.data) setCsrf(identity.data.csrf); }, [identity.data]);
  useEffect(() => { const listener = () => { setExpired(true); client.clear(); window.location.assign('/officer/login?expired=1'); }; window.addEventListener('session-expired', listener); return () => window.removeEventListener('session-expired', listener); }, [client]);
  useEffect(() => { if (message) { const timer = setTimeout(() => setMessage(''), 5000); return () => clearTimeout(timer); } }, [message]);
  const logout = async () => { await post('/auth/logout', {}); setCsrf(''); client.clear(); window.location.assign('/officer/login'); };
  if (identity.isPending) return <Loading />;
  if (!identity.data) return <Login expired={expired} onSuccess={data => { setCsrf(data.csrf); client.clear(); client.setQueryData(['identity'], data); }} />;
  return <Auth.Provider value={{ user: identity.data.user, logout }}><Toast.Provider value={setMessage}><Routes><Route element={<Shell />}><Route path="/dashboard" element={<Dashboard />} /><Route path="/complaints" element={<Complaints />} /><Route path="/complaints/:id" element={<CaseDetail />} /><Route path="/institutions" element={<Institutions />} /><Route path="/institutions/:id" element={<InstitutionDetail />} /><Route path="/overlaps" element={<Overlaps />} /><Route path="/overlaps/:id" element={<OverlapDetail />} /><Route path="/alerts" element={<Alerts />} /><Route path="/audit-logs" element={<Audit />} /><Route path="/reports" element={<Reports />} /><Route path="/account-requests" element={<AccountRequestsManager />} /><Route path="*" element={<Navigate to="/dashboard" replace />} /></Route></Routes>{message && <div className="toast" role="status"><CheckCheck size={18} />{message}<button aria-label="Dismiss notification" className="icon-button" onClick={() => setMessage('')}><X size={16} /></button></div>}</Toast.Provider></Auth.Provider>;
}

function Login({ onSuccess, expired }: { onSuccess: (data: { user: User; csrf: string }) => void; expired: boolean }) {
  const [show, setShow] = useState(false);
  const [regMode, setRegMode] = useState<'none' | 'student' | 'college_rep' | 'officer'>('none');
  const [successReq, setSuccessReq] = useState<{ id: number; email: string; type: string; message: string } | null>(null);
  const navigate = useNavigate();

  const loginMutation = useMutation({
    mutationFn: (data: { email: string; password: string }) => post<{ user: User; csrf: string }>('/auth/login', data),
    onSuccess: data => { onSuccess(data); navigate('/dashboard'); }
  });

  const regMutation = useMutation({
    mutationFn: ({ endpoint, payload }: { endpoint: string; payload: Record<string, unknown> }) =>
      post<{ ok: boolean; id: number; status: string; message: string }>(endpoint, payload),
    onSuccess: (data, vars) => {
      setSuccessReq({
        id: data.id,
        email: String(vars.payload.email),
        type: vars.endpoint.includes('student') ? 'Student Registration' : vars.endpoint.includes('college-rep') ? 'College Representative (ASOP)' : 'AICTE Officer Account',
        message: data.message
      });
    }
  });

  function submitLogin(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    loginMutation.mutate({ email: String(form.get('email')), password: String(form.get('password')) });
  }

  function submitRegistration(e: FormEvent<HTMLFormElement>, endpoint: string) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const payload = Object.fromEntries(form.entries());
    regMutation.mutate({ endpoint, payload });
  }

  return (
    <div className="login">
      <div className="dot-field" aria-hidden="true" />
      <div className="login-brand-wrapper">
        <img src="/logo.png" alt="OneCase — AICTE Intelligent Institution Complaint Coordination & Tracking System" className="login-logo-img" />
      </div>

      <main className="login-card">
        {successReq ? (
          <div className="login-success-box">
            <div className="login-success-icon"><ShieldCheck size={28} /></div>
            <h2 className="login-success-title">Request Submitted</h2>
            <p className="login-success-desc">
              Your request has been securely persisted in the database and is currently <strong>pending administrative verification</strong>.
            </p>
            <div className="login-success-details">
              <div><span className="label">Request ID:</span><span className="val">#{successReq.id}</span></div>
              <div><span className="label">Account Type:</span><span className="val">{successReq.type}</span></div>
              <div><span className="label">Registered Email:</span><span className="val">{successReq.email}</span></div>
              <div><span className="label">Status:</span><span className="val" style={{ color: '#38bdf8' }}>Pending Verification</span></div>
            </div>
            <p className="muted" style={{ fontSize: '11px', lineHeight: 1.5, margin: 0 }}>
              AICTE security standards require that institutional affiliations and identity be verified before active account provisioning.
            </p>
            <button
              type="button"
              className="button primary full"
              onClick={() => { setSuccessReq(null); setRegMode('none'); regMutation.reset(); }}
            >
              <ArrowLeft size={16} /> Return to Sign In
            </button>
          </div>
        ) : regMode === 'student' ? (
          <div>
            <button type="button" className="login-back-btn" onClick={() => { setRegMode('none'); regMutation.reset(); }}>
              <ArrowLeft size={15} /> Back to Sign In
            </button>
            <div className="login-icon"><GraduationCap size={26} /></div>
            <p className="eyebrow">STUDENT PORTAL</p>
            <h1>Register as Student</h1>
            <p className="login-form-desc">Provide your academic enrollment details for institutional verification.</p>
            <form onSubmit={e => submitRegistration(e, '/account-requests/student')}>
              <Field title="Full Name">
                <input name="name" placeholder="Full name as per official records" minLength={2} maxLength={120} required />
              </Field>
              <Field title="Email Address">
                <input name="email" type="email" placeholder="student@college.edu or personal email" minLength={5} maxLength={180} required />
              </Field>
              <Field title="College Name">
                <input name="college_name" placeholder="Full name of your institution" minLength={2} maxLength={200} required />
              </Field>
              <div className="form-row">
                <Field title="Enrollment / Roll Number">
                  <input name="roll_number" placeholder="Official roll/enrollment number" minLength={1} maxLength={60} required />
                </Field>
                <Field title="Academic Year">
                  <input name="academic_year" placeholder="e.g. 2023-2027 (3rd Year)" minLength={2} maxLength={30} required />
                </Field>
              </div>
              <Field title="Course / Department">
                <input name="department" placeholder="e.g. B.Tech Computer Science" minLength={2} maxLength={100} required />
              </Field>
              <Field title="Password" hint="Minimum 8 characters">
                <div className="password-input">
                  <input name="password" type={show ? 'text' : 'password'} placeholder="Create a password" minLength={8} maxLength={128} required />
                  <button type="button" aria-label={show ? 'Hide password' : 'Show password'} onClick={() => setShow(!show)}>
                    {show ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </Field>
              <FormError mutation={regMutation} />
              <button className="button primary full" disabled={regMutation.isPending}>
                {regMutation.isPending ? 'Submitting Request…' : 'Submit Student Registration'}
                <ArrowRight size={17} />
              </button>
            </form>
          </div>
        ) : regMode === 'college_rep' ? (
          <div>
            <button type="button" className="login-back-btn" onClick={() => { setRegMode('none'); regMutation.reset(); }}>
              <ArrowLeft size={15} /> Back to Sign In
            </button>
            <div className="login-icon"><Building2 size={26} /></div>
            <p className="eyebrow">INSTITUTIONAL LIAISON (ASOP)</p>
            <h1>Request College Access</h1>
            <p className="login-form-desc">Request authorization as a designated institutional representative for grievance redressal.</p>
            <form onSubmit={e => submitRegistration(e, '/account-requests/college-rep')}>
              <Field title="Full Name">
                <input name="name" placeholder="Full name of representative" minLength={2} maxLength={120} required />
              </Field>
              <Field title="Official Email Address">
                <input name="email" type="email" placeholder="official@institution.edu.in" minLength={5} maxLength={180} required />
              </Field>
              <Field title="College Name">
                <input name="college_name" placeholder="Name of affiliated institution" minLength={2} maxLength={200} required />
              </Field>
              <div className="form-row">
                <Field title="Employee / Representative ID" hint="Optional">
                  <input name="employee_id" placeholder="Official institution faculty/staff ID" maxLength={60} />
                </Field>
                <Field title="Designation">
                  <input name="designation" placeholder="e.g. Associate Professor & ASOP Officer" minLength={2} maxLength={100} required />
                </Field>
              </div>
              <Field title="Reason for Access" hint="State your institutional role and authorization">
                <textarea name="reason" placeholder="Explain your official role, appointment as ASOP liaison, or purpose of access…" minLength={10} maxLength={2000} rows={3} required />
              </Field>
              <Field title="Password" hint="Minimum 8 characters">
                <div className="password-input">
                  <input name="password" type={show ? 'text' : 'password'} placeholder="Create a password" minLength={8} maxLength={128} required />
                  <button type="button" aria-label={show ? 'Hide password' : 'Show password'} onClick={() => setShow(!show)}>
                    {show ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </Field>
              <FormError mutation={regMutation} />
              <button className="button primary full" disabled={regMutation.isPending}>
                {regMutation.isPending ? 'Submitting Request…' : 'Submit Access Request'}
                <ArrowRight size={17} />
              </button>
            </form>
          </div>
        ) : regMode === 'officer' ? (
          <div>
            <button type="button" className="login-back-btn" onClick={() => { setRegMode('none'); regMutation.reset(); }}>
              <ArrowLeft size={15} /> Back to Sign In
            </button>
            <div className="login-icon"><Briefcase size={26} /></div>
            <p className="eyebrow">AICTE BUREAU OFFICIALS</p>
            <h1>Request Officer Account</h1>
            <p className="login-form-desc">Apply for an officer workspace account. Submissions require administrative verification against bureau rosters.</p>
            <form onSubmit={e => submitRegistration(e, '/account-requests/officer')}>
              <Field title="Full Name">
                <input name="name" placeholder="Full name of officer" minLength={2} maxLength={120} required />
              </Field>
              <Field title="Official Email Address">
                <input name="email" type="email" placeholder="officer@aicte.gov.in" minLength={5} maxLength={180} required />
              </Field>
              <div className="form-row">
                <Field title="Employee ID" hint="Optional">
                  <input name="employee_id" placeholder="e.g. AICTE-RB-8841" maxLength={60} />
                </Field>
                <Field title="Designation">
                  <input name="designation" placeholder="e.g. Assistant Director" minLength={2} maxLength={100} required />
                </Field>
              </div>
              <Field title="Bureau / Department">
                <select name="bureau_code" required defaultValue="RB">
                  <option value="RB">Regulation Bureau (RB)</option>
                  <option value="PGRC">Public Grievance Redressal Cell (PGRC)</option>
                  <option value="AB">Approval Bureau (AB)</option>
                  <option value="PAPB">Policy & Academic Planning Bureau (PAPB)</option>
                </select>
              </Field>
              <Field title="Reason for Access" hint="State your bureau assignment or case coordination duties">
                <textarea name="reason" placeholder="Explain your official bureau duties, case triage responsibilities, or transfer coordination needs…" minLength={10} maxLength={2000} rows={3} required />
              </Field>
              <Field title="Password" hint="Minimum 8 characters">
                <div className="password-input">
                  <input name="password" type={show ? 'text' : 'password'} placeholder="Create a password" minLength={8} maxLength={128} required />
                  <button type="button" aria-label={show ? 'Hide password' : 'Show password'} onClick={() => setShow(!show)}>
                    {show ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </Field>
              <FormError mutation={regMutation} />
              <button className="button primary full" disabled={regMutation.isPending}>
                {regMutation.isPending ? 'Submitting Request…' : 'Submit Officer Account Request'}
                <ArrowRight size={17} />
              </button>
            </form>
          </div>
        ) : (
          <div>
            <div className="login-icon"><ShieldCheck size={26} /></div>
            <p className="eyebrow">OFFICER WORKSPACE</p>
            <h1>Officer sign in</h1>
            <p>Access your authorized bureau workspace and case records.</p>
            {(expired || location.search.includes('expired')) && (
              <div className="notice">Your session expired. Sign in to continue.</div>
            )}
            <form onSubmit={submitLogin}>
              <Field title="Email address">
                <input autoComplete="username" name="email" type="email" placeholder="officer@your-bureau.gov.in" required />
              </Field>
              <Field title="Password">
                <div className="password-input">
                  <input autoComplete="current-password" name="password" type={show ? 'text' : 'password'} placeholder="Enter your password" maxLength={1024} required />
                  <button type="button" aria-label={show ? 'Hide password' : 'Show password'} onClick={() => setShow(!show)}>
                    {show ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </Field>
              <FormError mutation={loginMutation} />
              <button className="button primary full" disabled={loginMutation.isPending}>
                {loginMutation.isPending ? 'Signing in…' : 'Sign in to workspace'}
                <ArrowRight size={17} />
              </button>
            </form>

            <div className="login-reg-section">
              <div className="login-reg-title">New to OneCase?</div>
              <div className="login-reg-options">
                <button type="button" className="login-reg-btn" onClick={() => { setRegMode('student'); regMutation.reset(); }}>
                  <div className="login-reg-btn-content">
                    <span className="login-reg-btn-icon"><GraduationCap size={17} /></span>
                    <span>Register as Student</span>
                  </div>
                  <ChevronRight size={16} className="login-reg-btn-arrow" />
                </button>
                <button type="button" className="login-reg-btn" onClick={() => { setRegMode('college_rep'); regMutation.reset(); }}>
                  <div className="login-reg-btn-content">
                    <span className="login-reg-btn-icon"><Building2 size={17} /></span>
                    <span>Request College Access</span>
                  </div>
                  <ChevronRight size={16} className="login-reg-btn-arrow" />
                </button>
                <button type="button" className="login-reg-btn" onClick={() => { setRegMode('officer'); regMutation.reset(); }}>
                  <div className="login-reg-btn-content">
                    <span className="login-reg-btn-icon"><Briefcase size={17} /></span>
                    <span>Request Officer Account</span>
                  </div>
                  <ChevronRight size={16} className="login-reg-btn-arrow" />
                </button>
              </div>
            </div>

            <div className="login-foot">
              <ShieldCheck size={15} /> Access for provisioned bureau officers only
            </div>
          </div>
        )}
      </main>
      <p className="login-bottom">AICTE Intelligent Institution Complaint Coordination & Tracking System</p>
      <div className="login-status-notice">
        <ShieldCheck size={15} />
        <span>Authorized Officer Portal · Accounts must be provisioned through administrative workflow</span>
      </div>
    </div>
  );
}

const nav = [{ path: '/dashboard', label: 'Overview', icon: LayoutDashboard }, { path: '/complaints', label: 'Complaints', icon: FolderOpen }, { path: '/institutions', label: 'Institutions', icon: Building2 }, { path: '/overlaps', label: 'Overlap review', icon: Link2 }, { path: '/alerts', label: 'Alerts', icon: Bell }, { path: '/audit-logs', label: 'Action logs', icon: Activity }, { path: '/reports', label: 'Reports', icon: FileCheck2 }];
function Shell() {
  const { user, logout } = useContext(Auth); const [mobile, setMobile] = useState(false);
  const [dark, setDark] = useState(() => localStorage.getItem('onecase-theme') === 'dark');
  const [logoutError, setLogoutError] = useState<Error | null>(null);
  const navigate = useNavigate(); const location = useLocation();
  const allNav = user.role === 'admin' ? [...nav, { path: '/account-requests', label: 'Account Requests', icon: UserCheck }] : nav;
  useEffect(() => { document.documentElement.dataset.theme = dark ? 'dark' : 'light'; localStorage.setItem('onecase-theme', dark ? 'dark' : 'light'); }, [dark]);
  useEffect(() => { setMobile(false); window.scrollTo(0, 0); }, [location.pathname]);
  const sidebar = <><Link to="/dashboard" className="brand"><img src="/logo.png" alt="OneCase Logo" className="sidebar-logo-img" /><div className="brand-title"><span className="brand-one">One</span><span className="brand-case">Case</span><span className="brand-badge">AICTE</span></div></Link><div className="workspace"><span className="workspace-icon"><Building2 size={19} /></span><div><strong>{user.bureau} workspace</strong><small>Complaint coordination</small></div><ChevronDown size={14} /></div><p className="nav-label">WORKSPACE</p><nav>{allNav.map(item => <NavLink to={item.path} key={item.path} className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}><item.icon size={19} />{item.label}{item.path === '/overlaps' && <span className="nav-dot" />}</NavLink>)}</nav><div className="sidebar-bottom"><div className="demo-note"><ShieldCheck size={18} /><strong>Authorized Workspace</strong><p>Real database persistence · Immutable action audit trail</p></div><div className="profile"><span className="avatar">{user.name.split(' ').map(n => n[0]).slice(0, 2).join('')}</span><div><strong>{user.name}</strong><small>{label(user.role)} · {user.bureau}</small></div><button aria-label="Sign out" className="icon-button" onClick={() => Promise.resolve(logout()).catch(e => setLogoutError(e))}><LogOut size={17} /></button></div></div></>;
  return <div className="app-shell"><a href="#main" className="skip-link">Skip to content</a><aside className="sidebar">{sidebar}</aside><Dialog.Root open={mobile} onOpenChange={setMobile}><Dialog.Portal><Dialog.Overlay className="overlay" /><Dialog.Content className="mobile-sidebar"><Dialog.Title className="sr-only">Workspace navigation</Dialog.Title><Dialog.Description className="sr-only">Navigate the OneCase workspace.</Dialog.Description><Dialog.Close className="mobile-close icon-button" aria-label="Close navigation"><X /></Dialog.Close>{sidebar}</Dialog.Content></Dialog.Portal></Dialog.Root><div className="main-shell"><header className="topbar"><div className="breadcrumb"><button aria-label="Open navigation" className="icon-button mobile-menu" onClick={() => setMobile(true)}><Menu size={20} /></button><span>Workspace</span><ChevronRight size={14} /><strong>{allNav.find(n => location.pathname.startsWith(n.path))?.label || 'Case details'}</strong></div><div className="topbar-actions"><form className="global-search" onSubmit={e => { e.preventDefault(); const value = new FormData(e.currentTarget).get('search'); navigate('/complaints?q=' + encodeURIComponent(String(value))); }}><Search size={16} /><input name="search" aria-label="Search cases or institutions" placeholder="Search cases or institutions…" /></form><button className="icon-button" aria-label={dark ? 'Use light theme' : 'Use dark theme'} onClick={() => setDark(!dark)}>{dark ? <Sun size={18} /> : <Moon size={18} />}</button><Link to="/alerts" className="icon-button" aria-label="Open alerts"><Bell size={19} /></Link><span className="topbar-avatar">{user.name[0]}</span></div></header><main id="main" className="main-content"><ErrorBox error={logoutError} /><Outlet /></main><footer className="footer"><span>OneCase · Institution complaint coordination</span><span><span className="status-dot" /> Authorized workspace · Asia/Kolkata (IST)</span></footer></div></div>;
}

function Filters({ status = false }: { status?: boolean }) {
  const [params, setParams] = useSearchParams(); const directory = useData<Directory>('/directory');
  const [search, setSearch] = useState(params.get('q') || '');
  useEffect(() => { setSearch(params.get('q') || ''); }, [params]);
  function update(key: string, value: string) { const next = new URLSearchParams(params); next.delete('cursor'); value ? next.set(key, value) : next.delete(key); setParams(next); }
  return <div className="filters"><form className="search-input" onSubmit={e => { e.preventDefault(); update('q', search); }}><Search size={16} /><input aria-label="Search records" placeholder="Search reference or institution…" value={search} onChange={e => setSearch(e.target.value)} /><button className="text-button" type="submit">Search</button></form><select aria-label="Filter bureau" value={params.get('bureau') || ''} onChange={e => update('bureau', e.target.value)}><option value="">All permitted bureaus</option>{directory.data?.bureaus.map(b => <option key={b.id} value={b.id}>{b.code}</option>)}</select>{status && <select aria-label="Filter status" value={params.get('status') || ''} onChange={e => update('status', e.target.value)}><option value="">All statuses</option>{['received', 'under_review', 'awaiting_information', 'disposed'].map(s => <option key={s} value={s}>{label(s)}</option>)}</select>}<select aria-label="Filter category" value={params.get('category') || ''} onChange={e => update('category', e.target.value)}><option value="">All categories</option>{directory.data?.categories.map(s => <option key={s}>{s}</option>)}</select><Field title="Received from"><input type="date" value={params.get('from') || ''} onChange={e => update('from', e.target.value)} /></Field><Field title="Received to"><input type="date" value={params.get('to') || ''} onChange={e => update('to', e.target.value)} /></Field>{params.size > 0 && <button className="text-button" onClick={() => setParams({})}><X size={14} /> Clear filters</button>}</div>;
}

function Dashboard() {
  const { user } = useContext(Auth); const [params] = useSearchParams();
  const query = useData<Summary>('/dashboard/summary?' + params); const data = query.data;
  const scope = params.toString(); const list = (extra: string) => '/complaints?' + [scope, extra].filter(Boolean).join('&');
  return (
    <>
      <Heading eyebrow="YOUR WORKSPACE, AT A GLANCE" title={`Good ${new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 17 ? 'afternoon' : 'evening'}, ${user.name.split(' ')[0]}`} description="A clear view of every case that needs your attention." action={<NewComplaint />} />
      <Filters />
      <ErrorBox error={query.error} retry={() => query.refetch()} />
      {query.isPending ? <Loading /> : data && (
        <>
          <div className="scope-caption"><span><span className="status-dot" />Current authorized receipt cohort</span><span>Updated {date(data.asOf, true)} IST</span></div>
          <div className="stats">
            {[
              { name: 'Total complaints', value: data.total, icon: FileText, href: list(''), caption: 'Within selected receipt cohort', tone: 'blue' },
              { name: 'Active cases', value: data.active, icon: FolderOpen, href: list('active=true'), caption: 'Received, reviewing, or awaiting info', tone: 'emerald' },
              { name: 'Overdue cases', value: data.overdue, icon: Clock3, href: list('overdue=true'), caption: 'Active cases past their due date', tone: 'orange' },
              { name: 'Awaiting overlap review', value: data.pending_pairs, icon: Link2, href: '/overlaps?' + [scope, 'state=pending'].filter(Boolean).join('&'), caption: 'Possible pairs · human review required', tone: 'cyan' },
            ].map(stat => (
              <Link className="stat-card" key={stat.name} to={stat.href}>
                <div><span>{stat.name}</span><span className={`stat-icon ${stat.tone}`}><stat.icon size={19} /></span></div>
                <strong>{stat.value.toLocaleString('en-IN')}</strong>
                <p>{stat.caption}<ArrowRight size={14} /></p>
              </Link>
            ))}
          </div>
          <section className="card trend-card">
            <div className="card-heading">
              <div>
                <h2>Complaints received and disposal events</h2>
                <p>Eight weekly buckets · Monday boundaries · Asia/Kolkata</p>
              </div>
              <span className="subtle-tag">Event period</span>
            </div>
            {data.total === 0 ? (
              <div className="empty" style={{ padding: '48px 16px' }}>
                <Clock3 size={32} />
                <h3>No complaint activity recorded in database</h3>
                <p>Weekly trend data will populate as actual complaints are received and disposed within your authorized bureau scope.</p>
              </div>
            ) : (
              <>
                <div className="chart-legend">
                  <span><i className="received-key" /> Received</span>
                  <span><i className="disposed-key" /> Disposal events</span>
                </div>
                <div className="chart" aria-label="Weekly complaint trends">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={data.trend} margin={{ top: 10, right: 12, left: -25, bottom: 0 }}>
                      <defs>
                        <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#0062d2" stopOpacity={0.24} />
                          <stop offset="100%" stopColor="#0062d2" stopOpacity={0.01} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 5" vertical={false} stroke="var(--border)" />
                      <XAxis dataKey="week" axisLine={false} tickLine={false} tick={{ fill: 'var(--muted)', fontSize: 11 }} dy={10} />
                      <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fill: 'var(--muted)', fontSize: 11 }} />
                      <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, color: 'var(--text)' }} />
                      <Area type="monotone" name="Disposal events" dataKey="disposed" stroke="#0062d2" strokeWidth={2.5} fill="url(#area)" isAnimationActive={false} />
                      <Line type="monotone" name="Received" dataKey="received" stroke="#0284c7" strokeWidth={2} strokeDasharray="5 5" dot={false} isAnimationActive={false} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
                <details className="chart-data">
                  <summary>View accessible data table and scope</summary>
                  <p>Received counts follow the selected receipt filters. Disposal counts follow the same bureau, institution and category scope, using disposal event dates. A case disposed twice contributes two events.</p>
                  <table>
                    <thead><tr><th>Week beginning</th><th>Received</th><th>Disposal events</th></tr></thead>
                    <tbody>{data.trend.map(t => <tr key={t.week}><td>{t.week}</td><td>{t.received}</td><td>{t.disposed}</td></tr>)}</tbody>
                  </table>
                </details>
              </>
            )}
          </section>
          <div className="dashboard-bottom">
            <section className="card">
              <div className="card-heading">
                <div><h2>Cases requiring attention</h2><p>Ordered by urgency, priority, and deadline</p></div>
                <Link to={list('active=true')} className="text-button">View all <ArrowRight size={14} /></Link>
              </div>
              {data.attention.length ? data.attention.map(c => <Link to={`/complaints/${c.id}`} className="attention-row" key={c.id}><span className={`case-icon ${c.deadline_condition}`}><FileText size={18} /></span><div className="grow"><div className="row-title"><strong>{c.reference}</strong><Badge value={c.deadline_condition} /></div><p>{c.institution.name}</p><small>{c.category} · {c.bureau} · {c.owner}</small><div className="next-action">{c.next_action}</div></div><ChevronRight size={15} /></Link>) : <Empty title="Your queue is clear">No active complaints requiring attention in your authorized scope.</Empty>}
            </section>
            <section className="card">
              <div className="card-heading">
                <div><h2>Recent case actions</h2><p>Recorded activity in your selected scope</p></div>
                <Link to="/audit-logs" className="text-button">View logs <ArrowRight size={14} /></Link>
              </div>
              <div className="activity-list">
                {data.recent.map(e => <div className="activity-row" key={e.id}><span className="activity-mark"><Check size={12} /></span><div><p><strong>{e.actor}</strong> · {e.summary}</p><Link to={`/complaints/${e.complaint_id}`}>{e.reference}</Link><small>{date(e.created_at, true)} IST</small></div></div>)}
                {!data.recent.length && <Empty title="No recent actions">Activity will be logged automatically as cases are processed.</Empty>}
              </div>
              <div className="card-callout"><ShieldCheck size={18} /><div><strong>Every action leaves an immutable record</strong><p>Ownership, decisions, and case history stay connected.</p></div></div>
            </section>
          </div>
          <div className="policy-note"><CircleHelp size={15} />{data.policy}</div>
        </>
      )}
    </>
  );
}

function CaseTable({ items }: { items: Case[] }) {
  if (!items.length) return <Empty title="No complaints match this view">Adjust your filters or register a new complaint.</Empty>;
  return <div className="table-scroll"><table><thead><tr><th>Case / institution</th><th>Category</th><th>Status</th><th>Accountable owner</th><th>Deadline</th><th aria-label="Open case" /></tr></thead><tbody>{items.map(c => <tr key={c.id}><td><Link className="case-link" to={`/complaints/${c.id}`}>{c.reference}</Link><span className="cell-secondary">{c.institution.name}</span><small>Received {date(c.received_at)}</small></td><td>{c.category}<span className="cell-secondary"><Badge value={c.priority} /></span></td><td><Badge value={c.status} /></td><td>{c.owner}<span className="cell-secondary">{c.bureau}</span></td><td><Badge value={c.deadline_condition} /><span className="cell-secondary">{date(c.due_at)}</span></td><td><Link to={`/complaints/${c.id}`} aria-label={`Open ${c.reference}`}><ChevronRight size={17} /></Link></td></tr>)}</tbody></table></div>;
}
function Complaints() {
  const [params, setParams] = useSearchParams(); const query = useData<Page<Case>>('/complaints?' + params);
  const setCursor = (value: string | null) => { const next = new URLSearchParams(params); value ? next.set('cursor', value) : next.delete('cursor'); setParams(next); };
  return <><Heading eyebrow="CASE MANAGEMENT" title="Complaints" description="Connected records. Clear ownership. A complete history." action={<NewComplaint />} /><Filters status /><ErrorBox error={query.error} retry={() => query.refetch()} /><section className="card">{query.isPending ? <Loading /> : query.data && <><div className="card-heading"><h2>Authorized complaints <span className="count">{query.data.total}</span></h2><a className="button secondary small" href={'/api/reports/complaints.csv?' + params}><ArrowDownToLine size={15} /> Export CSV</a></div><CaseTable items={query.data.items} /><Pager page={query.data} cursor={params.get('cursor')} setCursor={setCursor} /></>}</section></>;
}

function NewComplaint() {
  const { user } = useContext(Auth); const [open, setOpen] = useState(false); const navigate = useNavigate();
  const directory = useData<Directory>('/directory'); const schools = useData<Page<Institution>>('/institutions?limit=100');
  const key = useRef(crypto.randomUUID());
  const mutation = useMutation({ mutationFn: (data: Record<string, unknown>) => post<Case>('/complaints', data, 'POST', { 'Idempotency-Key': key.current }), onSuccess: async c => { setOpen(false); key.current = crypto.randomUUID(); navigate(`/complaints/${c.id}`); } });
  const client = useQueryClient();
  if (!['officer', 'lead'].includes(user.role)) return null;
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const values = Object.fromEntries(new FormData(e.currentTarget));
    mutation.mutate({ ...values, institution_id: Number(values.institution_id), owner_id: Number(values.owner_id), received_at: new Date(String(values.received_at)).toISOString(), due_at: values.due_at ? new Date(String(values.due_at)).toISOString() : null }, { onSuccess: () => { client.invalidateQueries(); } });
  }
  return <Modal title="Register a complaint" description="Select a verified institution and assign an accountable officer." open={open} onOpenChange={setOpen} trigger={<button className="button primary"><Plus size={17} /> New complaint</button>}><form onSubmit={submit} className="form-grid"><ErrorBox error={directory.error || schools.error} /><Field title="Institution"><select name="institution_id" required defaultValue=""><option value="" disabled>Select institution</option>{schools.data?.items.map(i => <option key={i.id} value={i.id}>{i.name}{!i.verified ? ' (identity unverified)' : ''}</option>)}</select></Field><div className="form-row"><Field title="Category"><select name="category" required>{directory.data?.categories.map(c => <option key={c}>{c}</option>)}</select></Field><Field title="Priority"><select name="priority" defaultValue="normal">{['low', 'normal', 'high', 'urgent'].map(p => <option key={p} value={p}>{label(p)}</option>)}</select></Field></div><Field title="Complaint description"><textarea name="description" rows={5} minLength={20} maxLength={20000} placeholder="Describe the issue, relevant dates, and supporting details…" required /></Field><Field title="Accountable officer"><select name="owner_id" defaultValue={user.id} required>{directory.data?.officers.filter(o => o.bureau_id === user.bureau_id && (user.role === 'lead' || o.id === user.id)).map(o => <option key={o.id} value={o.id}>{o.name} · {o.bureau}</option>)}</select></Field><div className="form-row"><Field title="Receipt date and time" hint="Your browser's local timezone"><input name="received_at" type="datetime-local" defaultValue={new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16)} required /></Field><Field title="Explicit deadline (optional)" hint="Your browser's local timezone"><input name="due_at" type="datetime-local" /></Field></div><Field title="Deadline reason" hint="Required when setting an explicit deadline. No official policy is implied."><input name="deadline_reason" maxLength={1000} /></Field><Field title="Next action"><input name="next_action" placeholder="What should happen next?" minLength={3} maxLength={500} required /></Field><FormError mutation={mutation} /><button className="button primary" disabled={mutation.isPending || !directory.data || !schools.data}>{mutation.isPending ? 'Registering…' : 'Register complaint'}<ArrowRight size={16} /></button></form></Modal>;
}

function CaseDetail() {
  const { id } = useParams(); const query = useData<Case>(`/complaints/${id}`); const history = useData<Page<Event>>(`/complaints/${id}/actions?limit=100`);
  const [mode, setMode] = useState(''); const [tab, setTab] = useState('overview'); const { user } = useContext(Auth);
  const retry = useSave(() => post(`/complaints/${id}/matching/retry`, { version: query.data?.version }));
  const ack = useSave((transfer: number) => post(`/transfers/${transfer}/acknowledge`, {}));
  if (query.isPending) return <Loading />;
  if (!query.data) return <><Link className="back-link" to="/complaints"><ArrowLeft size={16} /> All complaints</Link><ErrorBox error={query.error} retry={() => query.refetch()} /></>;
  const c = query.data;
  return <><Link className="back-link" to="/complaints"><ArrowLeft size={16} /> All complaints</Link><Heading eyebrow="COMPLAINT RECORD" title={c.reference} description={c.institution.name} action={<div className="button-row">{c.can_transfer && <button className="button secondary" onClick={() => setMode('transfer')}>Transfer case <ArrowRight size={16} /></button>}{c.can_edit && <button className="button primary" onClick={() => setMode('action')}><Plus size={16} /> Record action</button>}</div>} /><div className="case-status-row"><Badge value={c.status} /><Badge value={c.priority} /><span className="muted">Received {date(c.received_at, true)} IST · Revision {c.version}</span></div><div className="case-layout"><div><div className="tabs" role="tablist" aria-label="Case sections">{['overview', 'history', 'evidence'].map(t => <button key={t} role="tab" id={`tab-${t}`} aria-controls="case-panel" aria-selected={tab === t} onClick={() => setTab(t)} className={tab === t ? 'selected' : ''}>{label(t)}</button>)}</div><section className="card detail-card" id="case-panel" role="tabpanel" aria-labelledby={`tab-${tab}`}>{tab === 'overview' ? <><div className="card-heading"><h2>Complaint overview</h2>{c.can_edit && <button className="text-button" onClick={() => setMode('edit')}>Edit details</button>}</div><p className="description-text">{c.description}</p><dl className="detail-grid"><div><dt>Institution identity</dt><dd><Link to={`/institutions/${c.institution.id}`}>{c.institution.name}</Link><span className="cell-secondary">{c.institution.external_id || 'No external identifier'} · {c.institution.verified ? 'Verified' : 'Unverified'}</span></dd></div><div><dt>Category</dt><dd>{c.category}</dd></div><div><dt>Region</dt><dd>{c.institution.region}</dd></div><div><dt>Current bureau</dt><dd>{c.bureau}</dd></div></dl><div className="section-divider" /><h2>Matching progress</h2><div className="matching-progress"><Badge value={c.matching_state} /><p>{c.matching_state === 'completed' ? 'Local semantic retrieval and reranking completed. Related cases remain subject to human review.' : c.matching_error || 'The matching worker will process this complaint. Pending processing does not mean there are no overlaps.'}</p></div><FormError mutation={retry} />{c.matching_state === 'failed' && c.can_edit && <button className="button secondary" disabled={retry.isPending} onClick={() => retry.mutate(undefined)}><RefreshCw size={15} /> Retry matching</button>}<Link className="text-button" to={`/overlaps?institution=${c.institution.id}`}>View authorized overlap queue <ArrowRight size={14} /></Link></> : tab === 'history' ? <><h2>Case action history</h2><p className="muted">Append-only events · Timestamps displayed in IST</p><ErrorBox error={history.error} />{history.isPending ? <Loading /> : <EventList items={history.data?.items || []} />}</> : <Evidence c={c} />}</section></div><aside className="case-aside"><section className="card"><div className="card-heading"><h2>Accountability</h2><ShieldCheck size={18} /></div><div className="owner-block"><span className="avatar">{c.owner.split(' ').map(s => s[0]).slice(0, 2).join('')}</span><div><strong>{c.owner}</strong><p>{c.bureau} · Accountable officer</p></div></div><div className="next-action-box"><p className="eyebrow">NEXT ACTION</p><p>{c.next_action}</p></div>{c.transfers?.filter(t => t.to_owner_id === user.id && !t.acknowledged_at && c.owner_id === user.id).map(t => <button className="button secondary full" key={t.id} onClick={() => ack.mutate(t.id)} disabled={ack.isPending}><Check size={15} /> Acknowledge transfer</button>)}<FormError mutation={ack} /></section><section className="card"><div className="card-heading"><h2>Deadline</h2><Clock3 size={18} /></div><div className="deadline-block"><Badge value={c.deadline_condition} /><strong>{date(c.due_at, true)}{c.due_at && ' IST'}</strong><p>{c.deadline_policy}</p><small>Status changes do not pause the deadline. Reopening retains the existing deadline unless explicitly revised.</small></div></section>{c.can_edit && <section className="card"><div className="card-heading"><h2>Case lifecycle</h2></div><div className="padded"><p className="muted">Record a reason when changing this case's status.</p><button className="button secondary full" onClick={() => setMode('status')}>Change status <ChevronRight size={15} /></button></div></section>}</aside></div><CaseAction c={c} mode={mode} close={() => setMode('')} /></>;
}

function CaseAction({ c, mode, close }: { c: Case; mode: string; close: () => void }) {
  const directory = useData<Directory>('/directory'); const navigate = useNavigate();
  const mutation = useSave((data: Record<string, unknown>) => post(`/complaints/${c.id}${mode === 'edit' ? '' : '/' + (mode === 'action' ? 'actions' : mode)}`, { ...data, version: c.version }, mode === 'edit' ? 'PATCH' : 'POST'), () => { close(); if (mode === 'transfer') navigate('/complaints'); });
  useEffect(() => { mutation.reset(); }, [mode]); // Reset errors between actions.
  const title: Record<string, string> = { action: 'Record an action', transfer: 'Transfer responsibility', status: 'Change case status', edit: 'Edit case details' };
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); const values: Record<string, unknown> = Object.fromEntries(new FormData(e.currentTarget));
    if (mode === 'transfer') values.owner_id = Number(values.owner_id);
    mutation.mutate(values);
  }
  return <Modal title={title[mode] || ''} description={`${c.reference} · Current owner: ${c.owner} (${c.bureau}) · Version ${c.version}`} open={!!mode} onOpenChange={open => !open && close()}><form onSubmit={submit} className="form-grid">{mode === 'transfer' && <><div className="notice">Ownership changes immediately when saved. Recipient acknowledgement is recorded separately. Your continued access depends on your permissions.</div><Field title="Receiving accountable officer"><select name="owner_id" required defaultValue=""><option value="" disabled>Select receiving officer</option>{directory.data?.officers.filter(u => u.id !== c.owner_id).map(u => <option value={u.id} key={u.id}>{u.name} · {u.bureau}</option>)}</select></Field></>}{mode === 'status' && <Field title="New status"><select name="status" required>{c.allowed_transitions?.map(s => <option key={s} value={s}>{label(s)}</option>)}</select></Field>}{mode === 'edit' && <><Field title="Description"><textarea name="description" rows={6} defaultValue={c.description} required minLength={20} maxLength={20000} /></Field><Field title="Priority"><select name="priority" defaultValue={c.priority}>{['low', 'normal', 'high', 'urgent'].map(s => <option key={s} value={s}>{label(s)}</option>)}</select></Field></>}{['action', 'edit'].includes(mode) && <Field title="Next action"><input name="next_action" defaultValue={c.next_action} minLength={3} maxLength={500} required /></Field>}<Field title={mode === 'action' ? 'Action / remark' : 'Reason'} hint="This explanation becomes part of the permanent case history."><textarea name="reason" required minLength={5} maxLength={2000} rows={3} autoFocus /></Field><FormError mutation={mutation} /><button className="button primary" disabled={mutation.isPending}>{mutation.isPending ? 'Saving…' : mode === 'transfer' ? 'Confirm transfer' : 'Save to case history'}<Check size={16} /></button></form></Modal>;
}

function Evidence({ c }: { c: Case }) {
  const mutation = useSave((form: FormData) => api(`/complaints/${c.id}/attachments`, { method: 'POST', body: form }));
  const formRef = useRef<HTMLFormElement>(null);
  return <><h2>Case evidence</h2><p className="muted">Private files · PDF, PNG or JPEG · Maximum 8 MB per file</p>{c.attachments?.length ? c.attachments.map(a => <a className="attachment" href={`/api/attachments/${a.id}/download`} key={a.id}><FileText size={21} /><div><strong>{a.filename}</strong><small>{(a.size / 1024).toFixed(1)} KB · Authenticated download</small></div><ArrowDownToLine size={17} /></a>) : <Empty title="No evidence uploaded" />}{c.can_edit && <form ref={formRef} className="upload-form" onSubmit={e => { e.preventDefault(); const form = new FormData(e.currentTarget); form.set('version', String(c.version)); mutation.mutate(form, { onSuccess: () => formRef.current?.reset() }); }}><Field title="Upload supporting evidence"><input name="file" type="file" accept=".pdf,.png,.jpg,.jpeg" required /></Field><button className="button secondary" disabled={mutation.isPending}><Upload size={16} />{mutation.isPending ? 'Uploading…' : 'Upload evidence'}</button><FormError mutation={mutation} /></form>}</>;
}

function EventList({ items }: { items: Event[] }) {
  const [expanded, setExpanded] = useState<number | null>(null);
  if (!items.length) return <Empty title="No actions in this view" />;
  return <div className="event-list">{items.map(e => <div className="event" key={e.id}><div className="event-row"><button className="event-toggle" aria-expanded={expanded === e.id} aria-controls={`event-${e.id}`} onClick={() => setExpanded(expanded === e.id ? null : e.id)}><ChevronRight className={expanded === e.id ? 'rotated' : ''} size={16} /><div className="event-info"><strong>{e.summary}</strong><span>{e.actor} · {date(e.created_at, true)} IST</span></div><Badge value={e.outcome} /></button><Link className="event-case" to={`/complaints/${e.complaint_id}`}>{e.reference}</Link></div>{expanded === e.id && <div id={`event-${e.id}`} className="event-detail"><dl><div><dt>Event type</dt><dd>{label(e.kind)}</dd></div><div><dt>Reason / remarks</dt><dd>{e.reason || 'No additional remark recorded.'}</dd></div><div><dt>Original UTC timestamp</dt><dd>{e.created_at}</dd></div><div><dt>Severity</dt><dd>{label(e.severity)}</dd></div></dl>{Object.keys(e.changes).length > 0 && <pre>{JSON.stringify(e.changes, null, 2)}</pre>}</div>}</div>)}</div>;
}

function NewInstitution() {
  const { user } = useContext(Auth); const [open, setOpen] = useState(false);
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => post<Institution>('/institutions', data, 'POST'),
    onSuccess: () => { setOpen(false); client.invalidateQueries(); }
  });
  if (!['officer', 'lead', 'admin'].includes(user.role)) return null;
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const values = Object.fromEntries(new FormData(e.currentTarget));
    mutation.mutate({
      name: String(values.name),
      external_id: values.external_id ? String(values.external_id).trim() : null,
      region: String(values.region),
      address: String(values.address),
      verified: values.verified === 'on'
    });
  }
  return <Modal title="Register institution" description="Add an institution to the canonical directory with its official AICTE identifier." open={open} onOpenChange={setOpen} trigger={<button className="button primary"><Plus size={17} /> Add institution</button>}><form onSubmit={submit} className="form-grid"><Field title="Institution name"><input name="name" placeholder="Official institution name" minLength={3} maxLength={200} required /></Field><div className="form-row"><Field title="AICTE Permanent ID" hint="Official identifier (e.g. 1-123456789)"><input name="external_id" placeholder="Optional external identifier" maxLength={60} /></Field><Field title="Region"><select name="region" required defaultValue="North"><option value="North">North</option><option value="West">West</option><option value="South">South</option><option value="East">East</option><option value="Central">Central</option><option value="Northwest">Northwest</option><option value="Southwest">Southwest</option></select></Field></div><Field title="Campus address"><input name="address" placeholder="Campus location, City, State" minLength={5} maxLength={300} required /></Field>{['lead', 'admin'].includes(user.role) && <label className="checkbox-field"><input name="verified" type="checkbox" /> <span>Mark as officially verified AICTE identifier</span></label>}<FormError mutation={mutation} /><button className="button primary" disabled={mutation.isPending}>{mutation.isPending ? 'Registering…' : 'Register institution'}<ArrowRight size={16} /></button></form></Modal>;
}

function Institutions() {
  const [params, setParams] = useSearchParams(); const query = useData<Page<Institution>>('/institutions?' + params);
  return <><Heading eyebrow="CANONICAL DIRECTORY" title="Institutions" description="Start with a verified identity. Explore the case history you are authorized to see." action={<NewInstitution />} /><form className="filters" onSubmit={e => { e.preventDefault(); setParams({ q: String(new FormData(e.currentTarget).get('q')) }); }}><div className="search-input"><Search size={16} /><input name="q" aria-label="Search institutions" defaultValue={params.get('q') || ''} placeholder="Institution name or verified identifier…" /><button className="text-button">Search</button></div></form><ErrorBox error={query.error} retry={() => query.refetch()} />{query.isPending ? <Loading /> : <div className="institution-grid">{query.data?.items.map(i => <Link key={i.id} to={`/institutions/${i.id}`} className="card institution-card"><span className="institution-icon"><Building2 size={25} /></span><Badge value={i.verified ? 'verified' : 'unverified'} /><h2>{i.name}</h2><p>{i.external_id || 'Identifier pending verification'}</p><div><span>{i.region} region</span><ArrowRight size={17} /></div></Link>)}</div>}{query.data && !query.data.items.length && <Empty title="No institutions in directory">Authorized institutions must be registered or imported with verified AICTE identifiers.</Empty>}{query.data && <Pager page={query.data} cursor={params.get('cursor')} setCursor={value => { const next = new URLSearchParams(params); value ? next.set('cursor', value) : next.delete('cursor'); setParams(next); }} />}</>;
}
function InstitutionDetail() {
  const { id } = useParams(); const school = useData<Institution>(`/institutions/${id}`);
  const [params, setParams] = useSearchParams();
  const query = useData<Page<Case>>(`/institutions/${id}/complaints?` + params);
  return <><Link className="back-link" to="/institutions"><ArrowLeft size={16} /> Institution directory</Link>{school.data ? <><Heading eyebrow="INSTITUTION PROFILE" title={school.data.name} description={school.data.address} /><div className="institution-banner"><Building2 size={24} /><strong>{school.data.external_id || 'Identifier not verified'}</strong><Badge value={school.data.verified ? 'verified' : 'unverified'} /><span>{school.data.region} region</span></div><section className="card"><div className="card-heading"><div><h2>Permitted complaint history</h2><p>Shared institution identity does not prove complaints are related.</p></div></div><ErrorBox error={query.error} />{query.data ? <><CaseTable items={query.data.items} /><Pager page={query.data} cursor={params.get('cursor')} setCursor={value => setParams(value ? { cursor: value } : {})} /></> : <Loading />}</section></> : <ErrorBox error={school.error} />}</>;
}

function Overlaps() {
  const [params, setParams] = useSearchParams(); const query = useData<Page<Pair>>('/overlaps?' + params);
  return <><Heading eyebrow="CROSS-BUREAU COORDINATION" title="Overlap review" description="Possible relationships, surfaced for a reasoned human decision." /><div className="notice"><Link2 size={18} /><span>Suggestions preserve both original complaints. Scores indicate relevance and are not probabilities of duplication or findings of misconduct.</span></div><Filters /><div className="filter-tabs">{['', 'pending', 'related', 'unrelated'].map(s => <button key={s} className={(params.get('state') || '') === s ? 'selected' : ''} onClick={() => { const next = new URLSearchParams(params); next.delete('cursor'); s ? next.set('state', s) : next.delete('state'); setParams(next); }}>{s ? label(s) : 'All suggestions'}</button>)}</div><ErrorBox error={query.error} retry={() => query.refetch()} />{query.isPending ? <Loading /> : query.data && <>{query.data.items.length ? query.data.items.map(p => <Link className="card pair-card" to={`/overlaps/${p.id}`} key={p.id}><div className="pair-heading"><Badge value={p.band} /><Badge value={p.state} />{p.stale && <Badge value="stale" />}<span className="muted">{p.a.institution.name}</span><strong>{(p.evidence.hybrid * 100).toFixed(1)}<small>/100 relevance</small></strong></div><div className="pair-cases"><div><span>{p.a.reference} · {p.a.bureau}</span><h3>{p.a.category}</h3><p>{p.a.owner} · {label(p.a.status)}</p></div><Link2 size={22} /><div><span>{p.b.reference} · {p.b.bureau}</span><h3>{p.b.category}</h3><p>{p.b.owner} · {label(p.b.status)}</p></div><ArrowRight size={20} /></div></Link>) : <Empty title="No reviewable pairs in your scope">Processing may still be pending. Case detail shows matching status; missing model setup is shown as a failure rather than zero matches. Reviewers need explicit access to both cases.</Empty>}<Pager page={query.data} cursor={params.get('cursor')} setCursor={value => { const next = new URLSearchParams(params); value ? next.set('cursor', value) : next.delete('cursor'); setParams(next); }} /></>}</>;
}
function OverlapDetail() {
  const { id } = useParams(); const query = useData<Pair>(`/overlaps/${id}`);
  const mutation = useSave((data: Record<string, unknown>) => post(`/overlaps/${id}/review`, { ...data, version: query.data?.version }));
  if (query.isPending) return <Loading />;
  if (!query.data) return <ErrorBox error={query.error} retry={() => query.refetch()} />;
  const p = query.data;
  return <><Link className="back-link" to="/overlaps"><ArrowLeft size={16} /> Overlap queue</Link><Heading eyebrow="HUMAN REVIEW REQUIRED" title="Possible overlap" description={p.a.institution.name} /><div className="case-status-row"><Badge value={p.band} /><Badge value={p.state} />{p.stale && <Badge value="stale" />}</div><div className="compare-grid">{[p.a, p.b].map(c => <section className="card compare-case" key={c.id}><div className="card-heading"><Link to={`/complaints/${c.id}`} className="case-link">{c.reference}</Link><Badge value={c.status} /></div><span className="eyebrow">{c.bureau} · {c.category}</span><h2>{c.owner}</h2><p className="description-text">{c.description}</p><div className="next-action-box"><p className="eyebrow">NEXT ACTION</p><p>{c.next_action}</p></div><small>Received {date(c.received_at)} · Content revision {c.content_revision}</small></section>)}</div><section className="card evidence-card"><div className="card-heading"><h2>Why this pair was suggested</h2><strong className="relevance-score">{(p.evidence.hybrid * 100).toFixed(1)}<small>/100 hybrid relevance</small></strong></div><p>{p.evidence.explanation}</p><div className="signal-grid"><div><span>Semantic cosine (raw)</span><strong>{p.evidence.cosine.toFixed(3)}</strong></div><div><span>Cross-Encoder raw logit</span><strong>{p.evidence.reranker_raw.toFixed(3)}</strong></div><div><span>Normalized relevance signal</span><strong>{p.evidence.signals.reranker.toFixed(3)}</strong></div></div><div className="tags">{p.evidence.shared_terms.map(t => <span className="subtle-tag" key={t}>{t}</span>)}</div><details className="model-details"><summary>Model versions, input revisions, and limitations</summary><p>{p.evidence.bundle.embedding.model} · {p.evidence.bundle.embedding.revision}</p><p>{p.evidence.bundle.reranker.model} · {p.evidence.bundle.reranker.revision}</p><p>Scoring: {p.evidence.bundle.scoring_version} · top-k {p.evidence.bundle.top_k} · Input revisions {JSON.stringify(p.evidence.revisions)}</p><p>Truncation: {p.evidence.truncated ? 'Input exceeded tokenizer limits; incomplete evidence requires caution.' : 'No input truncation detected.'}</p><p>Demo weights and thresholds are unvalidated. Normalized signals are not calibrated probabilities.</p></details></section><section className="card review-form"><h2>Record a review decision</h2>{p.stale && <div className="notice">Case content changed after matching. Wait for refreshed evidence before recording a new review.</div>}{p.can_review && !p.stale ? <form onSubmit={e => { e.preventDefault(); mutation.mutate(Object.fromEntries(new FormData(e.currentTarget))); }}><Field title="Decision"><select name="decision" required><option value="related">Mark related</option><option value="unrelated">Mark unrelated</option></select></Field><Field title="Reason"><textarea name="reason" minLength={5} maxLength={2000} rows={3} placeholder="Explain the evidence supporting your decision…" required /></Field><FormError mutation={mutation} /><button className="button primary" disabled={mutation.isPending}><CheckCheck size={17} />{mutation.isPending ? 'Saving…' : 'Record decision'}</button></form> : <p className="muted">A designated reviewer with access to both cases can record the decision.</p>}{p.reviews?.map(r => <div className="review-history" key={r.id}><Badge value={r.decision} /><strong>{r.reviewer}</strong><small>{date(r.created_at, true)} IST</small><p>{r.reason}</p></div>)}</section></>;
}

type Alert = { id: number; kind: string; message: string; complaint_id: number; read_at: string | null; created_at: string };
function Alerts() {
  const [params, setParams] = useSearchParams(); const query = useData<Page<Alert>>('/notifications?' + params); const mutation = useSave((id: number) => post(`/notifications/${id}`, {}, 'PATCH'));
  return <><Heading eyebrow="WORK THAT NEEDS ATTENTION" title="Alerts" description="Persistent assignment, deadline, and coordination notifications." /><ErrorBox error={query.error} retry={() => query.refetch()} /><FormError mutation={mutation} /><section className="card">{query.isPending ? <Loading /> : query.data && <>{query.data.items.length ? query.data.items.map(a => <div className={`alert-row ${a.read_at ? '' : 'unread'}`} key={a.id}><span className="alert-icon"><Bell size={19} /></span><div className="grow"><Badge value={a.kind} /><p>{a.message}</p><small>{date(a.created_at, true)} IST</small>{a.complaint_id && <Link to={`/complaints/${a.complaint_id}`} className="text-button">Open case <ArrowRight size={14} /></Link>}</div>{!a.read_at ? <button className="button secondary small" disabled={mutation.isPending} onClick={() => mutation.mutate(a.id)}><Check size={14} /> Mark read</button> : <span className="muted">Read</span>}</div>) : <Empty title="You're all caught up">New alerts appear here when the monitoring worker runs.</Empty>}<Pager page={query.data} cursor={params.get('cursor')} setCursor={value => setParams(value ? { cursor: value } : {})} /></>}</section></>;
}
function Audit() {
  const [params, setParams] = useSearchParams(); const query = useData<Page<Event>>('/audit-logs?' + params);
  return <><Heading eyebrow="ACCOUNTABILITY & HISTORY" title="Action logs" description="Explore authorized events. Historical actions are preserved as recorded." /><Filters /><div className="audit-layout"><aside className="card audit-filters"><h2><SlidersHorizontal size={16} /> Event filters</h2><Field title="Action type"><select value={params.get('kind') || ''} onChange={e => { const next = new URLSearchParams(params); next.delete('cursor'); e.target.value ? next.set('kind', e.target.value) : next.delete('kind'); setParams(next); }}><option value="">All actions</option>{['registered', 'updated', 'action_recorded', 'transferred', 'acknowledged', 'status_changed', 'reopened', 'overlap_reviewed', 'deadline_alert', 'evidence_added'].map(s => <option key={s} value={s}>{label(s)}</option>)}</select></Field><form onSubmit={e => { e.preventDefault(); const next = new URLSearchParams(params); const actor = String(new FormData(e.currentTarget).get('actor')); next.delete('cursor'); actor ? next.set('actor', actor) : next.delete('actor'); setParams(next); }}><Field title="Actor"><input name="actor" placeholder="Officer name" defaultValue={params.get('actor') || ''} /></Field><button className="button secondary full">Apply actor filter</button></form><p className="muted">Filters apply before pagination. All times are displayed in Asia/Kolkata. Expand an event for its UTC timestamp.</p></aside><section className="card"><div className="card-heading"><h2>Recorded events <span className="count">{query.data?.total ?? '—'}</span></h2></div><ErrorBox error={query.error} retry={() => query.refetch()} />{query.isPending ? <Loading /> : query.data && <><EventList items={query.data.items} /><Pager page={query.data} cursor={params.get('cursor')} setCursor={value => { const next = new URLSearchParams(params); value ? next.set('cursor', value) : next.delete('cursor'); setParams(next); }} /></>}</section></div></>;
}
function Reports() {
  const [params] = useSearchParams(); const query = useData<Summary>('/dashboard/summary?' + params);
  return <><Heading eyebrow="SCOPED OPERATIONAL REPORTING" title="Reports" description="Traceable counts from the same records used throughout your workspace." action={<a className="button primary" href={'/api/reports/complaints.csv?' + params}><ArrowDownToLine size={16} /> Export complaint register</a>} /><Filters /><ErrorBox error={query.error} retry={() => query.refetch()} />{query.data && <><div className="compare-grid"><section className="card report-card"><h2>Current receipt cohort</h2><dl>{[['Total complaints', query.data.total], ['Active cases', query.data.active], ['Overdue cases', query.data.overdue], ['Human-confirmed related pairs', query.data.confirmed_pairs], ['Pairs awaiting review', query.data.pending_pairs]].map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{value}</dd></div>)}</dl></section><section className="card report-card"><h2>Active case ageing</h2><p className="muted">Elapsed days since receipt · Current state as of {date(query.data.asOf, true)} IST</p>{query.data.ageing.map(a => <div className="age-row" key={a.label}><span>{a.label}</span><div><i style={{ width: `${query.data!.active ? a.count / query.data!.active * 100 : 0}%` }} /></div><strong>{a.count}</strong></div>)}</section></div><section className="card report-card"><h2>Interpretation and export scope</h2><p>The export contains only authorized complaints matching the selected filters. Active means any case that is not disposed. Overdue means an active case with a due timestamp earlier than this report's current time.</p><p>Pair counts require access to both complaints; at least one must belong to the selected cohort. Confirmed means a human marked the pair related. Machine scores alone never count as confirmation.</p><p>{query.data.policy}</p></section></>}</>;
}

function AccountRequestsManager() {
  const [status, setStatus] = useState<string>('pending');
  const [type, setType] = useState<string>('');
  const query = useData<{ items: AccountRequest[]; total: number }>(`/account-requests?${status ? `status=${status}` : ''}${type ? `&type=${type}` : ''}`);
  const [reviewModal, setReviewModal] = useState<{ req: AccountRequest; decision: 'approved' | 'rejected' } | null>(null);
  const client = useQueryClient();
  const toast = useContext(Toast);

  const reviewMutation = useMutation({
    mutationFn: ({ id, decision, reason }: { id: number; decision: string; reason: string }) =>
      post<AccountRequest>(`/account-requests/${id}/review`, { decision, reason }),
    onSuccess: () => {
      client.invalidateQueries();
      toast('Account request reviewed successfully.');
      setReviewModal(null);
    }
  });

  function handleReviewSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!reviewModal) return;
    const form = new FormData(e.currentTarget);
    reviewMutation.mutate({
      id: reviewModal.req.id,
      decision: reviewModal.decision,
      reason: String(form.get('reason'))
    });
  }

  return (
    <>
      <Heading
        eyebrow="ADMINISTRATIVE VERIFICATION"
        title="Account Requests"
        description="Review, verify institutional affiliation, and approve or reject access requests."
      />
      <div className="filter-tabs">
        {[
          { key: 'pending', label: 'Pending Verification' },
          { key: 'approved', label: 'Approved' },
          { key: 'rejected', label: 'Rejected' },
          { key: '', label: 'All Requests' }
        ].map(tab => (
          <button
            key={tab.key}
            className={status === tab.key ? 'selected' : ''}
            onClick={() => setStatus(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <ErrorBox error={query.error} retry={() => query.refetch()} />
      {query.isPending ? (
        <Loading />
      ) : query.data && (
        <>
          {query.data.items.length === 0 ? (
            <Empty title={`No ${status || ''} account requests found`} />
          ) : (
            <div className="req-grid">
              {query.data.items.map(req => (
                <div key={req.id} className="req-card">
                  <div className="req-header">
                    <div className="req-user">
                      <strong>{req.name}</strong>
                      <span>{req.email}</span>
                    </div>
                    <Badge value={req.status} tone={req.status === 'approved' ? 'completed' : req.status === 'rejected' ? 'failed' : 'pending'} />
                  </div>
                  <div className="req-body">
                    <div className="req-body-row">
                      <span className="label">Request Type:</span>
                      <span className="val">{req.request_type === 'student' ? 'Student' : req.request_type === 'college_rep' ? 'College Rep (ASOP)' : 'AICTE Officer'}</span>
                    </div>
                    {req.college_name && (
                      <div className="req-body-row">
                        <span className="label">College / Institution:</span>
                        <span className="val">{req.college_name}</span>
                      </div>
                    )}
                    {req.roll_number && (
                      <div className="req-body-row">
                        <span className="label">Roll / Enrollment No:</span>
                        <span className="val">{req.roll_number}</span>
                      </div>
                    )}
                    {req.department && (
                      <div className="req-body-row">
                        <span className="label">Department / Course:</span>
                        <span className="val">{req.department}</span>
                      </div>
                    )}
                    {req.academic_year && (
                      <div className="req-body-row">
                        <span className="label">Academic Year:</span>
                        <span className="val">{req.academic_year}</span>
                      </div>
                    )}
                    {req.employee_id && (
                      <div className="req-body-row">
                        <span className="label">Employee ID:</span>
                        <span className="val">{req.employee_id}</span>
                      </div>
                    )}
                    {req.designation && (
                      <div className="req-body-row">
                        <span className="label">Designation:</span>
                        <span className="val">{req.designation}</span>
                      </div>
                    )}
                    {req.bureau_code && (
                      <div className="req-body-row">
                        <span className="label">Bureau:</span>
                        <span className="val">{req.bureau_code}</span>
                      </div>
                    )}
                    {req.reason && (
                      <div style={{ marginTop: 4 }}>
                        <span className="label" style={{ display: 'block', marginBottom: 2 }}>Reason for Access:</span>
                        <p style={{ margin: 0, fontStyle: 'italic', color: '#cbd5e1' }}>{req.reason}</p>
                      </div>
                    )}
                    <div className="req-body-row" style={{ marginTop: 4 }}>
                      <span className="label">Submitted:</span>
                      <span className="val">{date(req.created_at, true)} IST</span>
                    </div>
                    {req.reviewed_at && (
                      <div className="req-body-row">
                        <span className="label">Reviewed:</span>
                        <span className="val">{date(req.reviewed_at, true)} by {req.reviewer_name || 'Admin'}</span>
                      </div>
                    )}
                    {req.reviewer_decision_reason && (
                      <div style={{ marginTop: 2 }}>
                        <span className="label">Decision Reason:</span>
                        <p style={{ margin: 0, color: '#fca5a5' }}>{req.reviewer_decision_reason}</p>
                      </div>
                    )}
                  </div>
                  {req.status === 'pending' && (
                    <div className="req-actions">
                      <button
                        type="button"
                        className="button primary small"
                        onClick={() => setReviewModal({ req, decision: 'approved' })}
                      >
                        <Check size={14} /> Approve & Provision
                      </button>
                      <button
                        type="button"
                        className="button secondary small"
                        onClick={() => setReviewModal({ req, decision: 'rejected' })}
                      >
                        <X size={14} /> Reject
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {reviewModal && (
        <Modal
          title={reviewModal.decision === 'approved' ? 'Approve Account Request' : 'Reject Account Request'}
          description={`Applicant: ${reviewModal.req.name} (${reviewModal.req.email}) · Type: ${reviewModal.req.request_type}`}
          open={!!reviewModal}
          onOpenChange={open => !open && setReviewModal(null)}
        >
          <form onSubmit={handleReviewSubmit} className="form-grid">
            <Field
              title="Verification & Review Decision Reason"
              hint={reviewModal.decision === 'approved'
                ? "Document how applicant's identity and organizational affiliation were verified."
                : "Provide the reason for rejecting this account request."}
            >
              <textarea
                name="reason"
                required
                minLength={5}
                maxLength={2000}
                rows={4}
                autoFocus
                placeholder={reviewModal.decision === 'approved'
                  ? "e.g. Identity and enrollment verified against official college register."
                  : "e.g. Incomplete documentation or unauthorized designation."}
              />
            </Field>
            <FormError mutation={reviewMutation} />
            <button
              type="submit"
              className={`button ${reviewModal.decision === 'approved' ? 'primary' : 'secondary'}`}
              disabled={reviewMutation.isPending}
            >
              {reviewMutation.isPending ? 'Recording…' : reviewModal.decision === 'approved' ? 'Confirm Approval & Create User' : 'Confirm Rejection'}
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}
