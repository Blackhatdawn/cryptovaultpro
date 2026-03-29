/**
 * Runtime configuration loader.
 * Fetches public config from backend /api/config.
 */

export interface RuntimeConfig {
  appUrl: string;
  apiBaseUrl: string;
  wsBaseUrl: string;
  socketIoPath: string;
  environment: string;
  version: string;
  preferRelativeApi?: boolean;
  sentry?: {
    dsn?: string;
    enabled?: boolean;
    environment?: string;
  };
  branding?: {
    siteName?: string;
    logoUrl?: string;
    supportEmail?: string;
  };
}

const DEFAULT_SOCKET_PATH = '/socket.io/';
const CONFIG_ENDPOINT = '/api/config';
const CONFIG_FETCH_TIMEOUT_MS = 2500;
const RUNTIME_CONFIG_STATE_EVENT = 'runtime-config-state-change';

export type RuntimeConfigLoadState = 'idle' | 'loading' | 'ready' | 'degraded';

let runtimeConfig: RuntimeConfig | null = null;
let runtimeConfigLoadState: RuntimeConfigLoadState = 'idle';


const setRuntimeConfigLoadState = (nextState: RuntimeConfigLoadState): void => {
  runtimeConfigLoadState = nextState;

  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(RUNTIME_CONFIG_STATE_EVENT, { detail: nextState }));
  }
};

export const RUNTIME_CONFIG_LOAD_STATE_EVENT = RUNTIME_CONFIG_STATE_EVENT;

const sanitizeBaseUrl = (value: string): string => {
  if (!value) {
    return '';
  }

  const [first] = value.split(',');
  return first.trim().replace(/%20/g, '');
};

const normalizeBaseUrl = (value: string): string => {
  const sanitized = sanitizeBaseUrl(value);
  return sanitized.replace(/\/+$/, '');
};

const deriveWsBaseUrl = (baseUrl: string): string => {
  if (!baseUrl) {
    return '';
  }
  if (baseUrl.startsWith('https://')) {
    return `wss://${baseUrl.slice('https://'.length)}`;
  }
  if (baseUrl.startsWith('http://')) {
    return `ws://${baseUrl.slice('http://'.length)}`;
  }
  return baseUrl;
};

const getFallbackAppUrl = (): string => {
  if (typeof window !== 'undefined') {
    return normalizeBaseUrl(window.location.origin);
  }
  return '';
};

const getFallbackApiBaseUrl = (): string => normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL || '');

const getFallbackConfig = (): RuntimeConfig => ({
  appUrl: getFallbackAppUrl(),
  apiBaseUrl: getFallbackApiBaseUrl(),
  wsBaseUrl: '',
  socketIoPath: DEFAULT_SOCKET_PATH,
  environment: import.meta.env.MODE || 'development',
  version: import.meta.env.VITE_APP_VERSION || '1.0.0',
  preferRelativeApi: false,
  sentry: {
    dsn: import.meta.env.VITE_SENTRY_DSN || '',
    enabled: import.meta.env.VITE_ENABLE_SENTRY === 'true',
    environment: import.meta.env.MODE,
  },
});

const mergeConfig = (base: RuntimeConfig, incoming: Partial<RuntimeConfig>): RuntimeConfig => {
  // Prefer-relative is the safest default when a platform proxy is in front (Vercel rewrites).
  // Do not guess "dev" based on hostname; use backend-provided preferRelativeApi + build mode.
  const runtimeEnv = String(incoming.environment || base.environment || '').toLowerCase();
  const isProductionRuntime = runtimeEnv === 'production';

  const preferRelativeApi =
    Boolean(incoming.preferRelativeApi ?? base.preferRelativeApi) ||
    (import.meta.env.DEV && !isProductionRuntime);

  const merged: RuntimeConfig = {
    ...base,
    ...incoming,
    preferRelativeApi,
    sentry: { ...base.sentry, ...incoming.sentry },
    branding: { ...base.branding, ...incoming.branding },
  };

  merged.appUrl = normalizeBaseUrl(merged.appUrl || base.appUrl);
  merged.apiBaseUrl = preferRelativeApi
    ? ''
    : normalizeBaseUrl(merged.apiBaseUrl || base.apiBaseUrl);
  merged.socketIoPath = merged.socketIoPath || DEFAULT_SOCKET_PATH;
  
  // When using relative API (dev/preview), WebSocket should also use current origin
  if (preferRelativeApi) {
    merged.wsBaseUrl = '';
  } else {
    merged.wsBaseUrl = normalizeBaseUrl(
      merged.wsBaseUrl || deriveWsBaseUrl(merged.apiBaseUrl || base.apiBaseUrl || merged.appUrl)
    );
  }

  return merged;
};

const getCandidateConfigUrls = (): string[] => {
  const fallbackApiBase = getFallbackApiBaseUrl();
  const candidates = [CONFIG_ENDPOINT];

  if (fallbackApiBase) {
    candidates.push(`${fallbackApiBase}${CONFIG_ENDPOINT}`);
  }

  return Array.from(new Set(candidates));
};

export async function loadRuntimeConfig(): Promise<RuntimeConfig> {
  if (runtimeConfig) {
    return runtimeConfig;
  }

  setRuntimeConfigLoadState('loading');
  const fallback = getFallbackConfig();

  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(() => {
    controller.abort();
  }, CONFIG_FETCH_TIMEOUT_MS);

  try {
    let lastError: Error | null = null;

    for (const url of getCandidateConfigUrls()) {
      try {
        const response = await fetch(url, {
          method: 'GET',
          headers: { Accept: 'application/json' },
          credentials: 'include',
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Config request failed (${response.status}) at ${url}`);
        }

        const data = (await response.json()) as Partial<RuntimeConfig>;
        runtimeConfig = mergeConfig(fallback, data);
        setRuntimeConfigLoadState('ready');
        return runtimeConfig;
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));
      }
    }

    throw lastError ?? new Error('Runtime config fetch failed');
  } catch (error) {
    runtimeConfig = mergeConfig(fallback, {});
    setRuntimeConfigLoadState('degraded');
    return runtimeConfig;
  } finally {
    globalThis.clearTimeout(timeoutId);
  }
}

export function getRuntimeConfig(): RuntimeConfig | null {
  return runtimeConfig;
}

export function resolveApiBaseUrl(): string {
  if (runtimeConfig?.preferRelativeApi) {
    return '';
  }
  if (runtimeConfig?.apiBaseUrl) {
    return runtimeConfig.apiBaseUrl;
  }
  return getFallbackApiBaseUrl();
}

export function resolveAppUrl(): string {
  if (runtimeConfig?.appUrl) {
    return runtimeConfig.appUrl;
  }
  return getFallbackAppUrl();
}

export function resolveWsBaseUrl(): string {
  if (runtimeConfig?.wsBaseUrl) {
    return runtimeConfig.wsBaseUrl;
  }

  const apiBase = resolveApiBaseUrl();
  if (apiBase) {
    return deriveWsBaseUrl(apiBase);
  }

  return deriveWsBaseUrl(getFallbackAppUrl());
}

export function resolveSocketIoPath(): string {
  return runtimeConfig?.socketIoPath || DEFAULT_SOCKET_PATH;
}

export function resolveSentryConfig(): RuntimeConfig['sentry'] {
  return runtimeConfig?.sentry || getFallbackConfig().sentry;
}

export function resolveSupportEmail(): string {
  return runtimeConfig?.branding?.supportEmail || 'support@example.com';
}

export function getRuntimeConfigLoadState(): RuntimeConfigLoadState {
  return runtimeConfigLoadState;
}
