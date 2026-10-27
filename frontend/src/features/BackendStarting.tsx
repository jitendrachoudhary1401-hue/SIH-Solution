import { RefreshCw } from 'lucide-react';

export default function BackendStarting() {
  return <main className="not-found"><section className="card not-found-card" aria-labelledby="backend-starting-title">
    <img className="brand-logo" src="/onecase-emblem.png" alt="OneCase" />
    <p className="eyebrow">ONECASE · CONNECTING</p>
    <RefreshCw className="spin" size={48} aria-hidden="true" />
    <h1 id="backend-starting-title">Waking up OneCase</h1>
    <p>The service may be starting after being idle. This can take about a minute.</p>
    <p role="status">We’ll open your workspace automatically when it is ready.</p>
  </section></main>;
}
