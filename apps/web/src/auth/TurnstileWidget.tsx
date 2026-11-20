import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';

declare global {
  interface Window {
    turnstile?: {
      render: (target: HTMLElement, options: Record<string, unknown>) => string;
      remove: (widgetId: string) => void;
      reset?: (widgetId: string) => void;
    };
  }
}

const TEST_SITE_KEY = '1x00000000000000000000AA';

export interface TurnstileWidgetHandle {
  reset: () => void;
}

export const TurnstileWidget = forwardRef<
  TurnstileWidgetHandle,
  { onToken: (token: string) => void }
>(function TurnstileWidget({ onToken }, ref) {
  const target = useRef<HTMLDivElement>(null);
  const onTokenRef = useRef(onToken);
  const widgetIdRef = useRef<string | undefined>(undefined);
  const [status, setStatus] = useState('Loading human verification…');
  const [configured, setConfigured] = useState(true);
  onTokenRef.current = onToken;
  useImperativeHandle(ref, () => ({
    reset() {
      const widgetId = widgetIdRef.current;
      if (widgetId && window.turnstile?.reset) window.turnstile.reset(widgetId);
      onTokenRef.current('');
      setStatus('Complete the check to continue.');
    },
  }), []);

  useEffect(() => {
    if (import.meta.env.MODE === 'test') {
      onTokenRef.current('test-token');
      setStatus('Test verification ready');
      return;
    }
    const explicitKey = import.meta.env.VITE_TURNSTILE_SITE_KEY;
    if (!import.meta.env.DEV && !explicitKey) {
      onTokenRef.current('');
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
        callback: (token: string) => { onTokenRef.current(token); setStatus(''); },
        'expired-callback': () => { onTokenRef.current(''); setStatus('Verification expired. Try again.'); },
        'error-callback': () => { onTokenRef.current(''); setStatus('Human verification could not load.'); },
        theme: 'light',
      });
      widgetIdRef.current = widgetId;
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
      if (widgetId && window.turnstile) window.turnstile.remove(widgetId);
      if (widgetIdRef.current === widgetId) widgetIdRef.current = undefined;
    };
  }, []);
  return (
    <div
      className={`turnstile-field${configured ? '' : ' turnstile-field--unavailable'}`}
      role="group"
      aria-label="Human verification"
    >
      <div ref={target} className="turnstile-field__widget" />
      {configured && status && <span className="entrance-hint" role="status">{status}</span>}
    </div>
  );
});
