/**
 * usePriceWebSocket Hook
 * Manages WebSocket connection to real-time price stream
 * Handles reconnection, price updates, and connection status
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { toast } from 'sonner';
import { resolveWsBaseUrl } from '@/lib/runtimeConfig';

export interface PriceUpdate {
  type: 'price_update' | 'status' | 'connection' | 'pong' | 'keep_alive';
  prices?: Record<string, string>;
  state?: string;
  source?: string;
  timestamp?: string;
  message?: string;
}

export interface ConnectionStatus {
  isConnected: boolean;
  isConnecting: boolean;
  source: 'coincap' | 'binance' | null;
  lastUpdate: Date | null;
  pricesCached: number;
  error: string | null;
  reconnectAttempt: number;
}

interface UsePriceWebSocketOptions {
  url?: string;
  autoReconnect?: boolean;
  maxReconnectAttempts?: number;
  reconnectDelay?: number;
  onPriceUpdate?: (prices: Record<string, string>) => void;
  onStatusChange?: (status: ConnectionStatus) => void;
  verbose?: boolean;
}

const getDefaultUrl = (): string => {
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
};

export function usePriceWebSocket(options: UsePriceWebSocketOptions = {}) {
  const {
    url = getDefaultUrl(),
    autoReconnect = true,
    maxReconnectAttempts = 10,
    reconnectDelay = 1000,
    onPriceUpdate,
    onStatusChange,
    verbose = import.meta.env.DEV,
  } = options;

  const websocketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const [prices, setPrices] = useState<Record<string, string>>({});
  const [status, setStatus] = useState<ConnectionStatus>({
    isConnected: false,
    isConnecting: false,
    source: null,
    lastUpdate: null,
    pricesCached: 0,
    error: null,
    reconnectAttempt: 0,
  });

  const log = useCallback(
    (message: string, data?: any) => {
      if (verbose) {
        console.log(`[PriceWebSocket] ${message}`, data || '');
      }
    },
    [verbose]
  );

  const updateStatus = useCallback(
    (updates: Partial<ConnectionStatus>) => {
      setStatus((prev) => {
        const newStatus = { ...prev, ...updates };
        onStatusChange?.(newStatus);
        return newStatus;
      });
    },
    [onStatusChange]
  );

  const handlePriceUpdate = useCallback(
    (update: PriceUpdate) => {
      if (update.prices) {
        setPrices(update.prices);
        onPriceUpdate?.(update.prices);

        // Update last update time and source
        updateStatus({
          lastUpdate: new Date(),
          source: (update.source as any) || status.source,
          pricesCached: Object.keys(update.prices).length,
          error: null,
        });

        log('📊 Prices updated', Object.keys(update.prices).length);
      }
    },
    [onPriceUpdate, updateStatus, log, status.source]
  );

  const handleStatusUpdate = useCallback(
    (update: PriceUpdate) => {
      updateStatus({
        source: (update.source as any) || status.source,
        pricesCached: update.prices_cached || status.pricesCached,
        error: null,
      });

      log('🔄 Status update:', update.state);
    },
    [updateStatus, log, status.source, status.pricesCached]
  );

  const sendPing = useCallback(() => {
    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      websocketRef.current.send(JSON.stringify({ type: 'ping' }));
    }
  }, []);

  const connect = useCallback(() => {
    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    updateStatus({ isConnecting: true, error: null });
    log(`🔌 Connecting to ${url}`);

    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        log('✅ WebSocket connected');
        updateStatus({
          isConnected: true,
          isConnecting: false,
          error: null,
          reconnectAttempt: 0,
        });

        // Send initial ping to confirm connection
        sendPing();

        // Start ping interval to keep connection alive
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
        }
        pingIntervalRef.current = setInterval(sendPing, 30000); // 30s keep-alive
      };

      ws.onmessage = (event) => {
        try {
          const message: PriceUpdate = JSON.parse(event.data);

          switch (message.type) {
            case 'price_update':
              handlePriceUpdate(message);
              break;
            case 'status':
              handleStatusUpdate(message);
              break;
            case 'connection':
              log(`✅ ${message.message}`);
              break;
            case 'pong':
              // Keep-alive response
              break;
            case 'keep_alive':
              // Server sent keep-alive
              sendPing();
              break;
            default:
              log('Unknown message type:', message.type);
          }
        } catch (e) {
          console.error('[PriceWebSocket] Failed to parse message:', e);
        }
      };

      ws.onerror = (event) => {
        const error = 'WebSocket error';
        log('❌ ' + error, event);
        updateStatus({
          error,
          isConnected: false,
          isConnecting: false,
        });
      };

      ws.onclose = () => {
        log('🔌 WebSocket disconnected');
        updateStatus({
          isConnected: false,
          isConnecting: false,
        });

        // Clear ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
        }

        // Attempt reconnection
        if (autoReconnect && status.reconnectAttempt < maxReconnectAttempts) {
          const nextDelay = Math.min(
            reconnectDelay * Math.pow(2, status.reconnectAttempt),
            30000 // Max 30 second backoff
          );

          log(
            `📈 Reconnection attempt ${status.reconnectAttempt + 1}/${maxReconnectAttempts} in ${nextDelay}ms`
          );

          updateStatus({ reconnectAttempt: status.reconnectAttempt + 1 });

          reconnectTimeoutRef.current = setTimeout(connect, nextDelay);
        } else if (status.reconnectAttempt >= maxReconnectAttempts) {
          const error = 'Failed to reconnect after maximum attempts';
          log('❌ ' + error);
          updateStatus({ error });
          toast.error('Failed to establish price stream connection');
        }
      };

      websocketRef.current = ws;
    } catch (e) {
      const error = `Connection error: ${e}`;
      log('❌ ' + error);
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
    reconnectDelay,
    status.reconnectAttempt,
    updateStatus,
    log,
    sendPing,
    handlePriceUpdate,
    handleStatusUpdate,
  ]);

  const disconnect = useCallback(() => {
    log('🛑 Disconnecting WebSocket');

    // Clear timers
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
    }

    // Close WebSocket
    if (websocketRef.current) {
      websocketRef.current.close();
      websocketRef.current = null;
    }

    updateStatus({
      isConnected: false,
      isConnecting: false,
    });
  }, [log, updateStatus]);

  const getPrice = useCallback(
    (symbol: string): string | undefined => {
      return prices[symbol.toLowerCase()];
    },
    [prices]
  );

  // Auto-connect on mount (stable - only depends on url)
  useEffect(() => {
    const ws = new WebSocket(url);
    
    ws.onopen = () => {
      log('Connected');
      updateStatus({
        isConnected: true,
        isConnecting: false,
        error: null,
        reconnectAttempt: 0,
      });
    };

    ws.onmessage = (event) => {
      try {
        const message: PriceUpdate = JSON.parse(event.data);
        if (message.type === 'price_update' && message.prices) {
          setPrices(message.prices);
          onPriceUpdate?.(message.prices);
          setStatus(prev => ({
            ...prev,
            lastUpdate: new Date(),
            source: (message.source as any) || prev.source,
            pricesCached: Object.keys(message.prices!).length,
            error: null,
          }));
        }
      } catch (e) {
        // ignore parse errors
      }
    };

    ws.onerror = () => {
      updateStatus({ error: 'WebSocket error', isConnected: false, isConnecting: false });
    };

    ws.onclose = () => {
      updateStatus({ isConnected: false, isConnecting: false });
    };

    websocketRef.current = ws;

    return () => {
      ws.close();
      websocketRef.current = null;
    };
  }, [url, log, updateStatus, onPriceUpdate]);

  return {
    prices,
    status,
    connect,
    disconnect,
    getPrice,
    isConnected: status.isConnected,
    isConnecting: status.isConnecting,
  };
}
