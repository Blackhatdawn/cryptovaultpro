/**
 * Push Notification Service
 * Handles Firebase Cloud Messaging (FCM) for web push notifications.
 * Falls back gracefully when Firebase is not configured.
 */

import apiClient from '@/lib/apiClient';

// Firebase config from environment variables
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

const vapidKey = import.meta.env.VITE_FIREBASE_VAPID_KEY;

// Check if Firebase is configured
const isFirebaseConfigured = Boolean(
  firebaseConfig.apiKey &&
  firebaseConfig.projectId &&
  firebaseConfig.messagingSenderId &&
  firebaseConfig.appId &&
  vapidKey
);

let messaging: any = null;

/**
 * Initialize Firebase messaging (lazy load)
 */
async function initializeMessaging() {
  if (messaging) return messaging;
  if (!isFirebaseConfigured) {
    console.log('[Push] Firebase not configured - push notifications unavailable');
    return null;
  }

  try {
    const { initializeApp } = await import('firebase/app');
    const { getMessaging, getToken, onMessage } = await import('firebase/messaging');

    const app = initializeApp(firebaseConfig);
    messaging = getMessaging(app);

    // Send config to service worker
    if ('serviceWorker' in navigator) {
      const registration = await navigator.serviceWorker.ready;
      registration.active?.postMessage({
        type: 'FIREBASE_CONFIG',
        config: firebaseConfig,
      });
    }

    // Handle foreground messages
    onMessage(messaging, (payload) => {
      console.log('[Push] Foreground message:', payload);

      // Show browser notification even in foreground
      if (Notification.permission === 'granted') {
        new Notification(payload.notification?.title || 'CryptoVault', {
          body: payload.notification?.body || '',
          icon: '/logo.svg',
          data: payload.data,
        });
      }
    });

    return messaging;
  } catch (error) {
    console.warn('[Push] Firebase initialization failed:', error);
    return null;
  }
}

/**
 * Request notification permission and register FCM token
 */
export async function requestPushPermission(): Promise<{
  granted: boolean;
  token?: string;
  error?: string;
}> {
  // Check browser support
  if (!('Notification' in window) || !('serviceWorker' in navigator)) {
    return { granted: false, error: 'Push notifications not supported in this browser' };
  }

  // Request permission
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') {
    return { granted: false, error: 'Notification permission denied' };
  }

  if (!isFirebaseConfigured) {
    // Firebase not configured - still register the intent
    return {
      granted: true,
      error: 'Firebase not configured yet. Push notifications will activate once Firebase is set up.',
    };
  }

  try {
    const msg = await initializeMessaging();
    if (!msg) {
      return { granted: true, error: 'Firebase messaging unavailable' };
    }

    const { getToken } = await import('firebase/messaging');
    const registration = await navigator.serviceWorker.getRegistration('/firebase-messaging-sw.js');

    const token = await getToken(msg, {
      vapidKey,
      serviceWorkerRegistration: registration || undefined,
    });

    // Register token with backend
    await apiClient.post('/api/push/register-token', {
      token,
      platform: 'web',
    });

    console.log('[Push] Token registered successfully');
    return { granted: true, token };
  } catch (error: any) {
    console.error('[Push] Token registration failed:', error);
    return { granted: true, error: error.message || 'Failed to get push token' };
  }
}

/**
 * Check current push notification status
 */
export async function getPushStatus(): Promise<{
  enabled: boolean;
  permission: NotificationPermission;
  firebaseConfigured: boolean;
}> {
  return {
    enabled: Notification.permission === 'granted',
    permission: 'Notification' in window ? Notification.permission : 'denied',
    firebaseConfigured: isFirebaseConfigured,
  };
}

/**
 * Unregister from push notifications
 */
export async function unregisterPush(): Promise<void> {
  try {
    await apiClient.delete('/api/push/unregister-token');
  } catch {
    // Ignore errors
  }
}

/**
 * Register service worker for push notifications
 */
export async function registerServiceWorker(): Promise<void> {
  if (!('serviceWorker' in navigator)) return;

  try {
    await navigator.serviceWorker.register('/firebase-messaging-sw.js', {
      scope: '/',
    });
    console.log('[Push] Service worker registered');
  } catch (error) {
    console.warn('[Push] Service worker registration failed:', error);
  }
}
