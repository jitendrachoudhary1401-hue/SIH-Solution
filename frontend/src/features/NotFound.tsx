import { Link } from 'react-router-dom';
import { ArrowLeft, Search } from 'lucide-react';

export default function NotFound({destination}: {destination: string}) {
  return <section className="not-found" aria-label="Page not found"><div className="card not-found-card">
    <img className="brand-logo" src="/onecase-emblem.png" alt="OneCase" />
    <p className="eyebrow">ONECASE · PAGE NOT FOUND</p>
    <div className="not-found-number" aria-hidden="true">404</div>
    <Search size={30} aria-hidden="true" />
    <h1>We couldn’t find that page</h1>
    <p>The address may be incorrect, or the page may have moved. Check the link or return to your workspace.</p>
    <Link className="button primary" to={destination}><ArrowLeft size={18} />{destination === '/officer/login' ? 'Go to sign in' : 'Return to workspace'}</Link>
  </div></section>;
}
