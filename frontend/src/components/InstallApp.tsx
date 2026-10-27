import { useEffect, useState } from 'react';
import { Download } from 'lucide-react';
import { Modal } from './ui';

interface InstallPrompt extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

function inAppWindow() {
  return window.matchMedia('(display-mode: standalone)').matches ||
    window.matchMedia('(display-mode: minimal-ui)').matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true;
}

export default function InstallApp() {
  const [installed, setInstalled] = useState(inAppWindow);
  const [prompt, setPrompt] = useState<InstallPrompt | null>(null);
  const [help, setHelp] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const capture = (event: Event) => {
      event.preventDefault();
      setPrompt(event as InstallPrompt);
    };
    const complete = () => { setInstalled(true); setPrompt(null); setHelp(false); };
    const mode = window.matchMedia('(display-mode: standalone)');
    const changed = () => setInstalled(inAppWindow());
    window.addEventListener('beforeinstallprompt', capture);
    window.addEventListener('appinstalled', complete);
    mode.addEventListener('change', changed);
    return () => {
      window.removeEventListener('beforeinstallprompt', capture);
      window.removeEventListener('appinstalled', complete);
      mode.removeEventListener('change', changed);
    };
  }, []);

  async function install() {
    if (!prompt) { setHelp(true); return; }
    setBusy(true);
    try {
      await prompt.prompt();
      const choice = await prompt.userChoice;
      if (choice.outcome === 'accepted') { setInstalled(true); setHelp(false); }
    } catch { setHelp(true); }
    finally { setPrompt(null); setBusy(false); }
  }

  if (installed) return null;
  return <>
    <button className="button secondary install-app-button" onClick={() => void install()} disabled={busy}>
      <Download size={17} aria-hidden="true" />{busy ? 'Opening install…' : 'Install OneCase'}
    </button>
    <Modal title="Install OneCase" description="Open your workspace from your home screen or desktop." open={help} onOpenChange={setHelp}>
      <div className="install-app-help">
        <p><strong>iPhone or iPad:</strong> Open this page in Safari, tap Share, then Add to Home Screen. If offered, keep Open as Web App enabled and tap Add.</p>
        <p><strong>Android:</strong> Open this page in Chrome, open the browser menu, then choose Install app or Add to Home screen.</p>
        <p><strong>Computer:</strong> Open this page in Chrome or Edge and use the install icon in the address bar or the browser menu. In Safari on Mac, choose File → Add to Dock.</p>
        <p>If an install option is missing, open the HTTPS site in your regular browser rather than a private window or an in-app browser. If OneCase is already installed, open it from your apps.</p>
        <p className="muted">An internet connection is required to sign in and use case records.</p>
        {prompt && <button className="button primary" onClick={() => void install()} disabled={busy}>Install now</button>}
      </div>
    </Modal>
  </>;
}
