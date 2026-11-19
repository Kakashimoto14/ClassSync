import { capabilitiesFor, resolveAppMode, type AppMode } from './app-mode';

declare const __CLASSSYNC_APP_MODE__: AppMode;
declare const __CLASSSYNC_DEV_SERVER__: boolean;

export const devServer =
  typeof __CLASSSYNC_DEV_SERVER__ !== 'undefined' && __CLASSSYNC_DEV_SERVER__;

// Only the test runner uses the environment adapter. Distributable code receives
// immutable, validated constants from Vite; storage and URL parameters are excluded.
export const appMode =
  typeof __CLASSSYNC_APP_MODE__ !== 'undefined'
    ? __CLASSSYNC_APP_MODE__
    : import.meta.env.MODE === 'test'
      ? resolveAppMode({
          command: import.meta.env.DEV ? 'serve' : 'build',
          mode:
            import.meta.env.VITE_CLASSSYNC_MODE ?? (import.meta.env.DEV ? 'sandbox' : undefined),
          rolePreview: import.meta.env.VITE_ENABLE_ROLE_PREVIEW,
          presentationSample: import.meta.env.VITE_ENABLE_PRESENTATION_SAMPLE,
        })
      : (() => {
          throw new Error('Missing validated ClassSync build configuration.');
        })();

export const capabilities = capabilitiesFor(appMode);
// A distributable/institutional build always uses the connected access screen.
// Runtime preview flags are never consulted by AuthPage for its login entry.
export const institutionalAccessRequired =
  appMode === 'institutional' || (import.meta.env.PROD && appMode !== 'presentation');
export function requireLiveCapability() {
  if (!capabilities.liveRequests)
    throw Object.assign(new Error(capabilities.description), { status: 403 });
}

export async function liveFetch(...args: Parameters<typeof fetch>) {
  requireLiveCapability();
  return fetch(...args);
}
