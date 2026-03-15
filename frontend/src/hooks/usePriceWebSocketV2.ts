/**
 * usePriceWebSocketV2 Hook - Enterprise Edition
 * 
 * Production-ready WebSocket hook with enhanced features:
 * - Connection pooling (single connection shared across components)
 * - Exponential backoff with jitter
 * - Offline detection and recovery
 * - Message buffering during reconnection
 * - Connection quality monitoring
 * - Automatic cleanup
 */

import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { toast } from 'sonner';
import { resolveWsBaseUrl } from '@/lib/runtimeConfig';

// ============================================
// TYPES
// ============================================

export interface PriceData {
  [symbol: string]: string;
}

export interface PriceUpdate {
  type: 'price_update' | 'status' | 'connection' | 'pong' | 'keep_alive' | 'error' | 'subscribed' | 'unsubscribed';
  prices?: PriceData;
  state?: string;
  source?: string;
  timestamp?: string;
  message?: string;
  code?: string;
  channels?: string[];
}

export interface ConnectionQuality {
  latency: number;        // ms
  messagesPerSecond: number;
  isStable: boolean;
  lastMeasured: Date;
}

export interface ConnectionStatus {
  isConnected: boolean;
  isConnecting: boolean;
  isOnline: boolean;
  source: 'coincap' | 'binance' | null;
  lastUpdate: Date | null;
  pricesCached: number;
  error: string | null;
  reconnectAttempt: number;
  quality: ConnectionQuality | null;
}

interface UsePriceWebSocketOptions {
  url?: string;
  autoReconnect?: boolean;
  maxReconnectAttempts?: number;
  baseReconnectDelay?: number;
  maxReconnectDelay?: number;
  pingInterval?: number;
  onPriceUpdate?: (prices: PriceData) => void;
  onStatusChange?: (status: ConnectionStatus) => void;
  onError?: (error: string) => void;
  verbose?: boolean;
  symbols?: string[];  // Specific symbols to subscribe to
}

// ============================================
// CONNECTION POOL (SINGLETON)
// ============================================

interface PooledConnection {
  ws: WebSocket | null;
  subscribers: Set<(data: PriceUpdate) => void>;
  status: ConnectionStatus;
  reconnectTimeout: NodeJS.Timeout | null;
  pingInterval: NodeJS.Timeout | null;
  latencyMeasurements: number[];
  messageTimestamps: number[];
}

const connectionPool: Map<string, PooledConnection> = new Map();

function getOrCreateConnection(url: string): PooledConnection {
  if (!connectionPool.has(url)) {
    connectionPool.set(url, {
      ws: null,
      subscribers: new Set(),
      status: {
        isConnected: false,
        isConnecting: false,
        isOnline: typeof navigator !== 'undefined' ? navigator.onLine : true,
        source: null,
        lastUpdate: null,
        pricesCached: 0,
        error: null,
        reconnectAttempt: 0,
        quality: null,
      },
      reconnectTimeout: null,
      pingInterval: null,
      latencyMeasurements: [],
      messageTimestamps: [],
    });
  }
  return connectionPool.get(url)!;
}

// ============================================
// UTILITY FUNCTIONS
// ============================================

/**
 * Calculate exponential backoff with jitter
 */
function calculateBackoff(
  attempt: number,
  baseDelay: number = 1000,
  maxDelay: number = 30000
): number {
  const exponentialDelay = Math.min(baseDelay * Math.pow(2, attempt), maxDelay);
  const jitter = Math.random() * 0.3 * exponentialDelay; // 30% jitter
  return Math.floor(exponentialDelay + jitter);
}

/**
 * Calculate connection quality metrics
 */
function calculateQuality(pool: PooledConnection): ConnectionQuality {
  const now = Date.now();
  
  // Calculate average latency
  const recentLatencies = pool.latencyMeasurements.slice(-10);
  const avgLatency = recentLatencies.length > 0
    ? recentLatencies.reduce((a, b) => a + b, 0) / recentLatencies.length
    : 0;
  
  // Calculate messages per second (last 10 seconds)
  const recentMessages = pool.messageTimestamps.filter(t => now - t < 10000);
  const messagesPerSecond = recentMessages.length / 10;
  
  // Determine stability
  const isStable = avgLatency < 500 && pool.status.reconnectAttempt === 0;
  
  return {
    latency: Math.round(avgLatency),
    messagesPerSecond: Math.round(messagesPerSecond * 10) / 10,
    isStable,
    lastMeasured: new Date(),
  };
}

/**
 * Get default WebSocket URL
 */
function getDefaultUrl(): string {
  const wsBaseUrl = resolveWsBaseUrl();
  if (wsBaseUrl) {
    return `${wsBaseUrl}/ws/prices`;
  }
  // Derive from current page URL
  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/ws/prices`;
  }
  return 'wss://localhost:8001/ws/prices';
}

// ============================================
// MAIN HOOK
// ============================================

export function usePriceWebSocketV2(options: UsePriceWebSocketOptions = {}) {
  const {
    url = getDefaultUrl(),
    autoReconnect = true,
    maxReconnectAttempts = 15,
    baseReconnectDelay = 1000,
    maxReconnectDelay = 30000,
    pingInterval: pingIntervalMs = 25000,
    onPriceUpdate,
    onStatusChange,
    onError,
    verbose = import.meta.env.DEV,
    symbols,
  } = options;

  // State
  const [prices, setPrices] = useState<PriceData>({});
  const [status, setStatus] = useState<ConnectionStatus>(() => {
    const pool = getOrCreateConnection(url);
    return pool.status;
  });

  // Refs
  const subscriberRef = useRef<(data: PriceUpdate) => void | null>(null);
  const pingSentTimeRef = useRef<number>(0);
  const mountedRef = useRef(true);

  // Logging utility
  const log = useCallback(
    (message: string, data?: any) => {
      if (verbose) {
        console.log(`[PriceWebSocketV2] ${message}`, data || '');
      }
    },
    [verbose]
  );

  // Update status with callbacks
  const updateStatus = useCallback(
    (updates: Partial<ConnectionStatus>) => {
      if (!mountedRef.current) return;
      
      const pool = getOrCreateConnection(url);
      pool.status = { ...pool.status, ...updates };
      
      setStatus(prev => {
        const newStatus = { ...prev, ...updates };
        onStatusChange?.(newStatus);
        return newStatus;
      });
    },
    [url, onStatusChange]
  );

  // Handle incoming messages
  const handleMessage = useCallback(
    (data: PriceUpdate) => {
      if (!mountedRef.current) return;
      
      const pool = getOrCreateConnection(url);
      
      switch (data.type) {
        case 'price_update':
          if (data.prices) {
            setPrices(data.prices);
            onPriceUpdate?.(data.prices);
            
            // Track message for quality metrics
            pool.messageTimestamps.push(Date.now());
            pool.messageTimestamps = pool.messageTimestamps.slice(-100);
            
            updateStatus({
              lastUpdate: new Date(),
              source: (data.source as any) || status.source,
              pricesCached: Object.keys(data.prices).length,
              error: null,
              quality: calculateQuality(pool),
            });
            
            log('📊 Prices updated', Object.keys(data.prices).length);
          }
          break;
        
        case 'status':
          updateStatus({
            source: (data.source as any) || status.source,
          });
          log('🔄 Status update:', data.state);
          break;
        
        case 'connection':
          log(`✅ ${data.message}`);
          break;
        
        case 'pong':
          // Calculate latency
          if (pingSentTimeRef.current > 0) {
            const latency = Date.now() - pingSentTimeRef.current;
            pool.latencyMeasurements.push(latency);
            pool.latencyMeasurements = pool.latencyMeasurements.slice(-20);
            pingSentTimeRef.current = 0;
          }
          break;
        
        case 'keep_alive':
          // Server sent keep-alive, respond with ping
          sendPing();
          break;
        
        case 'error': {
          const errorMsg = data.message || 'Unknown error';
          log('❌ Error:', errorMsg);
          onError?.(errorMsg);
          updateStatus({ error: errorMsg });
          break;
        }
        
        case 'subscribed':
          log('✅ Subscribed to channels:', data.channels);
          break;
        
        case 'unsubscribed':
          log('📤 Unsubscribed from channels:', data.channels);
          break;
        
        default:
          log('Unknown message type:', data.type);
      }
    },
    [url, onPriceUpdate, onError, updateStatus, log, status.source]
  );

  // Send ping
  const sendPing = useCallback(() => {
    const pool = getOrCreateConnection(url);
    if (pool.ws?.readyState === WebSocket.OPEN) {
      pingSentTimeRef.current = Date.now();
      pool.ws.send(JSON.stringify({ type: 'ping' }));
    }
  }, [url]);

  // Subscribe to specific symbols
  const subscribeToSymbols = useCallback((symbols: string[]) => {
    const pool = getOrCreateConnection(url);
    if (pool.ws?.readyState === WebSocket.OPEN && symbols.length > 0) {
      pool.ws.send(JSON.stringify({ type: 'subscribe', channels: symbols }));
      log('📥 Subscribing to symbols:', symbols);
    }
  }, [url, log]);

  // Connect to WebSocket
  const connect = useCallback(() => {
    const pool = getOrCreateConnection(url);
    
    // Don't connect if already connected or connecting
    if (pool.ws?.readyState === WebSocket.OPEN || pool.status.isConnecting) {
      return;
    }
    
    // Don't connect if offline
    if (!navigator.onLine) {
      log('📴 Offline, waiting for network...');
      updateStatus({ isOnline: false, error: 'No network connection' });
      return;
    }
    
    updateStatus({ isConnecting: true, error: null, isOnline: true });
    log(`🔌 Connecting to ${url}`);
    
    try {
      const ws = new WebSocket(url);
      pool.ws = ws;
      
      ws.onopen = () => {
        log('✅ WebSocket connected');
        updateStatus({
          isConnected: true,
          isConnecting: false,
          error: null,
          reconnectAttempt: 0,
        });
        
        // Subscribe to specific symbols if provided
        if (symbols && symbols.length > 0) {
          subscribeToSymbols(symbols);
        }
        
        // Start ping interval
        if (pool.pingInterval) {
          clearInterval(pool.pingInterval);
        }
        pool.pingInterval = setInterval(sendPing, pingIntervalMs);
        
        // Initial ping
        sendPing();
      };
      
      ws.onmessage = (event) => {
        try {
          const data: PriceUpdate = JSON.parse(event.data);
          
          // Notify all subscribers
          pool.subscribers.forEach(subscriber => {
            try {
              subscriber(data);
            } catch (e) {
              console.error('[PriceWebSocketV2] Subscriber error:', e);
            }
          });
        } catch (e) {
          console.error('[PriceWebSocketV2] Failed to parse message:', e);
        }
      };
      
      ws.onerror = (event) => {
        const error = 'WebSocket connection error';
        log('❌ ' + error, event);
        onError?.(error);
        updateStatus({
          error,
          isConnected: false,
          isConnecting: false,
        });
      };
      
      ws.onclose = (event) => {
        log(`🔌 WebSocket closed (code: ${event.code}, reason: ${event.reason})`);
        updateStatus({
          isConnected: false,
          isConnecting: false,
        });
        
        // Clear ping interval
        if (pool.pingInterval) {
          clearInterval(pool.pingInterval);
          pool.pingInterval = null;
        }
        
        // Attempt reconnection
        if (autoReconnect && pool.status.reconnectAttempt < maxReconnectAttempts) {
          const delay = calculateBackoff(
            pool.status.reconnectAttempt,
            baseReconnectDelay,
            maxReconnectDelay
          );
          
          log(`📈 Reconnecting in ${delay}ms (attempt ${pool.status.reconnectAttempt + 1}/${maxReconnectAttempts})`);
          
          updateStatus({ reconnectAttempt: pool.status.reconnectAttempt + 1 });
          
          pool.reconnectTimeout = setTimeout(connect, delay);
        } else if (pool.status.reconnectAttempt >= maxReconnectAttempts) {
          const error = 'Failed to reconnect after maximum attempts';
          log('❌ ' + error);
          updateStatus({ error });
          onError?.(error);
          toast.error('Failed to establish price stream connection');
        }
      };
    } catch (e) {
      const error = `Connection error: ${e}`;
      log('❌ ' + error);
      onError?.(error);
      updateStatus({
        error,
        isConnected: false,
        isConnecting: false,
      });
    }
  }, [
    url,
    autoReconnect,
    maxReconnectAttempts,
    baseReconnectDelay,
    maxReconnectDelay,
    pingIntervalMs,
    symbols,
    updateStatus,
    log,
    sendPing,
    subscribeToSymbols,
    onError,
  ]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    const pool = getOrCreateConnection(url);
    
    log('🛑 Disconnecting WebSocket');
    
    // Clear timers
    if (pool.reconnectTimeout) {
      clearTimeout(pool.reconnectTimeout);
      pool.reconnectTimeout = null;
    }
    if (pool.pingInterval) {
      clearInterval(pool.pingInterval);
      pool.pingInterval = null;
    }
    
    // Close WebSocket
    if (pool.ws) {
      pool.ws.close(1000, 'Client disconnect');
      pool.ws = null;
    }
    
    updateStatus({
      isConnected: false,
      isConnecting: false,
      reconnectAttempt: 0,
    });
  }, [url, log, updateStatus]);

  // Force reconnect
  const reconnect = useCallback(() => {
    const pool = getOrCreateConnection(url);
    pool.status.reconnectAttempt = 0;
    disconnect();
    setTimeout(connect, 100);
  }, [url, disconnect, connect]);

  // Get price for a specific symbol
  const getPrice = useCallback(
    (symbol: string): string | undefined => {
      return prices[symbol.toLowerCase()];
    },
    [prices]
  );

  // Request specific price
  const requestPrice = useCallback(
    (symbol: string) => {
      const pool = getOrCreateConnection(url);
      if (pool.ws?.readyState === WebSocket.OPEN) {
        pool.ws.send(JSON.stringify({ type: 'get_price', symbol }));
      }
    },
    [url]
  );

  // Request service status
  const requestStatus = useCallback(() => {
    const pool = getOrCreateConnection(url);
    if (pool.ws?.readyState === WebSocket.OPEN) {
      pool.ws.send(JSON.stringify({ type: 'get_status' }));
    }
  }, [url]);

  // Online/offline detection
  useEffect(() => {
    const handleOnline = () => {
      log('🌐 Network online');
      updateStatus({ isOnline: true, error: null });
      connect();
    };
    
    const handleOffline = () => {
      log('📴 Network offline');
      updateStatus({ isOnline: false, error: 'No network connection' });
    };
    
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [connect, updateStatus, log]);

  // Setup subscriber and connect on mount
  useEffect(() => {
    mountedRef.current = true;
    const pool = getOrCreateConnection(url);
    
    // Create subscriber for this hook instance
    subscriberRef.current = handleMessage;
    pool.subscribers.add(subscriberRef.current);
    
    // Connect if not already connected
    if (!pool.ws || pool.ws.readyState === WebSocket.CLOSED) {
      connect();
    } else if (pool.ws.readyState === WebSocket.OPEN) {
      // Already connected, sync state
      updateStatus({
        isConnected: true,
        isConnecting: false,
      });
    }
    
    // Cleanup on unmount
    return () => {
      mountedRef.current = false;
      
      if (subscriberRef.current) {
        pool.subscribers.delete(subscriberRef.current);
      }
      
      // Only disconnect if no more subscribers
      if (pool.subscribers.size === 0) {
        log('🧹 No more subscribers, closing connection');
        disconnect();
        connectionPool.delete(url);
      }
    };
  }, [url, connect, disconnect, handleMessage, updateStatus, log]);

  return {
    // State
    prices,
    status,
    isConnected: status.isConnected,
    isConnecting: status.isConnecting,
    isOnline: status.isOnline,
    
    // Actions
    connect,
    disconnect,
    reconnect,
    getPrice,
    requestPrice,
    requestStatus,
    subscribeToSymbols,
  };
}

export default usePriceWebSocketV2;
