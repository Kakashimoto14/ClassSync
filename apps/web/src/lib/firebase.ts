import { configuredFirebase } from './firebase-config';

declare const __CLASSSYNC_AUTH_CONFIG_ENABLED__: boolean;

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};
export const firebaseReadiness = configuredFirebase(
  typeof __CLASSSYNC_AUTH_CONFIG_ENABLED__ === 'undefined' || __CLASSSYNC_AUTH_CONFIG_ENABLED__
    ? firebaseConfig
    : {},
);
export const firebaseApp = firebaseReadiness.app;
