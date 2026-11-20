import { act, render } from '@testing-library/react';
import { createRef as createReactRef } from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { TurnstileWidget } from './TurnstileWidget';

afterEach(() => {
  vi.unstubAllEnvs();
  delete window.turnstile;
});

it('keeps the widget mounted when its callback prop changes and calls the latest callback', () => {
  vi.stubEnv('MODE', 'production');
  vi.stubEnv('DEV', false);
  vi.stubEnv('VITE_TURNSTILE_SITE_KEY', 'local-test-site-key');
  const first = vi.fn();
  const latest = vi.fn();
  let options: Record<string, unknown> | undefined;
  const remove = vi.fn();
  window.turnstile = {
    render: vi.fn((_target, next) => {
      options = next;
      return 'widget-1';
    }),
    remove,
    reset: vi.fn(),
  };
  const view = render(<TurnstileWidget onToken={first} />);
  view.rerender(<TurnstileWidget onToken={latest} />);
  expect(window.turnstile.render).toHaveBeenCalledOnce();
  expect(remove).not.toHaveBeenCalled();
  act(() => (options?.callback as (token: string) => void)('verified-once'));
  expect(first).not.toHaveBeenCalled();
  expect(latest).toHaveBeenCalledWith('verified-once');
});

it('exposes an explicit reset without coupling reset to component renders', () => {
  vi.stubEnv('MODE', 'production');
  vi.stubEnv('DEV', false);
  vi.stubEnv('VITE_TURNSTILE_SITE_KEY', 'local-test-site-key');
  const reset = vi.fn();
  window.turnstile = {
    render: vi.fn(() => 'widget-2'),
    remove: vi.fn(),
    reset,
  };
  const ref = createReactRef<import('./TurnstileWidget').TurnstileWidgetHandle>();
  const view = render(<TurnstileWidget ref={ref} onToken={vi.fn()} />);
  expect(window.turnstile.reset).not.toHaveBeenCalled();
  act(() => ref.current?.reset());
  expect(reset).toHaveBeenCalledWith('widget-2');
  view.unmount();
  expect(reset).toHaveBeenCalledOnce();
});
