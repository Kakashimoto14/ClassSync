import { useEffect, useRef, useState } from 'react';

declare global {
  interface Window {
    turnstile?: {
      render: (target: HTMLElement, options: Record<string, unknown>) => string;
      remove: (widgetId: string) => void;
    };
  }
}

const TEST_SITE_KEY = '1x00000000000000000000AA';

export function TurnstileWidget({ onToken }: { onToken: (token: string) => void }) {
  const target = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState('Loading human verification…');
  const [configured, setConfigured] = useState(true);
  useEffect(() => {
    if (import.meta.env.MODE === 'test') {
      onToken('test-token');
      setStatus('Test verification ready');
      return;
    }
    const explicitKey = import.meta.env.VITE_TURNSTILE_SITE_KEY;
    if (!import.meta.env.DEV && !explicitKey) {
      onToken('');
      setConfigured(false);
      return;
    }
    const siteKey = explicitKey || TEST_SITE_KEY;
    let widgetId: string | undefined;
    let cancelled = false;
    const mount = () => {
      if (cancelled || !target.current || !window.turnstile) return;
      widgetId = window.turnstile.render(target.current, {
        sitekey: siteKey,
        callback: (token: string) => { onToken(token); setStatus('Verification complete'); },
        'expired-callback': () => { onToken(''); setStatus('Verification expired. Try again.'); },
        'error-callback': () => { onToken(''); setStatus('Human verification could not load.'); },
        theme: 'light',
      });
      setStatus('Complete the check to continue.');
    };
    const existing = document.querySelector<HTMLScriptElement>(
      'script[src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit"]',
    );
    if (window.turnstile) mount();
    else if (existing) existing.addEventListener('load', mount, { once: true });
    else {
      const script = document.createElement('script');
      script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
      script.async = true;
      script.defer = true;
      script.addEventListener('load', mount, { once: true });
      script.addEventListener('error', () => setStatus('Human verification could not load.'), {
        once: true,
      });
      document.head.appendChild(script);
    }
    return () => {
      cancelled = true;
      onToken('');
      if (widgetId && window.turnstile) window.turnstile.remove(widgetId);
    };
  }, [onToken]);
  return (
    <div
      className={`turnstile-field${configured ? '' : ' turnstile-field--unavailable'}`}
      role="group"
      aria-label="Human verification"
    >
      <div ref={target} className="turnstile-field__widget" />
      {configured && <span className="entrance-hint" role="status">{status}</span>}
    </div>
  );
}
