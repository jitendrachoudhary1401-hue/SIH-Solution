import { useEffect, useState } from 'react';
import { Download } from 'lucide-react';

interface InstallPrompt extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

function standalone() {
  return window.matchMedia('(display-mode: standalone)').matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true;
}

export default function InstallApp() {
  const [offer, setOffer] = useState<InstallPrompt | null>(null);
  const [installed, setInstalled] = useState(standalone);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const available = (event: Event) => {
      // Preserve the browser's own install promotion; also offer a direct click.
      if (typeof (event as InstallPrompt).prompt === 'function') setOffer(event as InstallPrompt);
    };
    const complete = () => { setInstalled(true); setOffer(null); };
    window.addEventListener('beforeinstallprompt', available);
    window.addEventListener('appinstalled', complete);
    return () => {
      window.removeEventListener('beforeinstallprompt', available);
      window.removeEventListener('appinstalled', complete);
    };
  }, []);

  async function install() {
    if (!offer || busy) return;
    setBusy(true);
    try {
      // Called directly from the click so Chrome retains user activation.
      await offer.prompt();
      const choice = await offer.userChoice;
      if (choice.outcome === 'accepted') setInstalled(true);
    } catch {
      // A browser may already have consumed or withdrawn this one-use offer.
    } finally { setOffer(null); setBusy(false); }
  }

  if (!offer || installed) return null;
  return <button className="button primary native-install-button" disabled={busy} onClick={() => void install()}>
    <Download size={17} aria-hidden="true" />{busy ? 'Opening installer…' : 'Install OneCase'}
  </button>;
}
