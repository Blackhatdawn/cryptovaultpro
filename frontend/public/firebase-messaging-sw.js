/* eslint-disable no-restricted-globals */
/* Firebase Cloud Messaging Service Worker */

// Import Firebase scripts (compat version for service workers)
importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.12.0/firebase-messaging-compat.js');

// Firebase config is injected from the main app via message
let firebaseConfig = null;

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'FIREBASE_CONFIG') {
    firebaseConfig = event.data.config;
    initializeFirebase();
  }
});

function initializeFirebase() {
  if (!firebaseConfig) return;

  firebase.initializeApp(firebaseConfig);
  const messaging = firebase.messaging();

  messaging.onBackgroundMessage((payload) => {
    console.log('[SW] Background message received:', payload);

    const notificationTitle = payload.notification?.title || 'CryptoVault';
    const notificationOptions = {
      body: payload.notification?.body || '',
      icon: '/logo.svg',
      badge: '/logo.svg',
      vibrate: [200, 100, 200],
      data: payload.data || {},
      tag: payload.data?.type || 'default',
      actions: [
        { action: 'open', title: 'View' },
        { action: 'dismiss', title: 'Dismiss' },
      ],
    };

    self.registration.showNotification(notificationTitle, notificationOptions);
  });
}

// Handle notification click
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  const data = event.notification.data || {};
  let targetUrl = '/dashboard';

  // Route based on notification type
  switch (data.type) {
    case 'price_alert':
      targetUrl = `/markets?symbol=${data.symbol || ''}`;
      break;
    case 'order_confirmation':
      targetUrl = '/transactions';
      break;
    case 'deposit_confirmation':
      targetUrl = '/wallet';
      break;
    case 'referral_reward':
      targetUrl = '/referrals';
      break;
    case 'transfer':
      targetUrl = '/transactions';
      break;
    default:
      targetUrl = '/dashboard';
  }

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // Focus existing window or open new one
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      return clients.openWindow(targetUrl);
    })
  );
});
