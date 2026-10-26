import { RefreshCw, ServerOff } from 'lucide-react';

export default function BackendUnavailable({checking, onRetry}: {checking: boolean; onRetry: () => void}) {
  return <main className="not-found"><section className="card not-found-card" aria-labelledby="backend-down-title">
    <img className="brand-logo" src="/logo.png" alt="AICTE" />
    <p className="eyebrow">ONECASE · SERVICE UNAVAILABLE</p>
    <ServerOff size={48} aria-hidden="true" />
    <h1 id="backend-down-title">Backend is down. Try again later.</h1>
    <p role="alert">You have been automatically signed out. Your workspace is locked until the connection is restored.</p>
    <p>When the service is available again, sign in to continue.</p>
    <button className="button primary" onClick={onRetry} disabled={checking}><RefreshCw size={18} />{checking ? 'Checking connection…' : 'Try again'}</button>
    <p className="outage-status" role="status">{checking ? 'Checking service availability.' : 'We’ll also check again automatically.'}</p>
  </section></main>;
}
