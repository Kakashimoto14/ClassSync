import { getApps, initializeApp, type FirebaseOptions } from 'firebase/app';
const fields = [
  'apiKey',
  'authDomain',
  'projectId',
  'storageBucket',
  'messagingSenderId',
  'appId',
] as const;
export function configuredFirebase(config: FirebaseOptions) {
  const missing = fields.filter((key) => !config[key]);
  if (missing.length)
    return {
      app: undefined,
      status: missing.length === fields.length ? 'not-configured' : 'incomplete',
      missing,
    };
  const existing = getApps().find((app) => app.name === '[DEFAULT]');
  if (
    existing &&
    (existing.options.projectId !== config.projectId || existing.options.appId !== config.appId)
  )
    return { app: undefined, status: 'configuration-mismatch', missing: [] };
  try {
    return { app: existing ?? initializeApp(config), status: 'initialized', missing: [] };
  } catch {
    return { app: undefined, status: 'initialization-failed', missing: [] };
  }
}
