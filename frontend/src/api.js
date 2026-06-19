/**
 * WillGuard API Service
 * ━━━━━━━━━━━━━━━━━━━━━
 * Connects the React frontend to the FastAPI backend.
 * Gracefully falls back to offline mode when backend is unreachable.
 */

const API_BASE = 'http://localhost:8000/api';
const WS_URL = 'ws://localhost:8000/ws';

let _wsConnection = null;
let _reconnectTimer = null;

/**
 * Make an API request with error handling.
 * Returns { ok, data, error }
 */
async function apiCall(method, path, body = null) {
  try {
    const options = {
      method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (body) options.body = JSON.stringify(body);

    const res = await fetch(`${API_BASE}${path}`, options);
    const data = await res.json();

    if (!res.ok) {
      return { ok: false, data: null, error: data.detail || 'Request failed' };
    }
    return { ok: true, data, error: null };
  } catch (err) {
    return { ok: false, data: null, error: 'Backend offline' };
  }
}

// ─── Auth ─────────────────────────────────────────────

export async function register(userData) {
  return apiCall('POST', '/auth/register', userData);
}

export async function login(email, password) {
  return apiCall('POST', '/auth/login', { email, password });
}

// ─── Trades ───────────────────────────────────────────

export async function submitTrade(trade, userId) {
  return apiCall('POST', '/trade', { ...trade, user_id: userId });
}

// ─── Portfolio ────────────────────────────────────────

export async function getPortfolio(userId) {
  return apiCall('GET', `/portfolio/${userId}`);
}

// ─── System Status ────────────────────────────────────

export async function getStatus(userId) {
  const params = userId ? `?user_id=${userId}` : '';
  return apiCall('GET', `/status${params}`);
}

// ─── Financial Will ───────────────────────────────────

export async function getWill(userId) {
  return apiCall('GET', `/will/${userId}`);
}

export async function updateWill(userId, willData) {
  return apiCall('PUT', `/will/${userId}`, willData);
}

// ─── Emergency Contacts ──────────────────────────────

export async function getContacts(userId) {
  return apiCall('GET', `/contacts/${userId}`);
}

// ─── Decision Ledger ─────────────────────────────────

export async function getLedger(userId, limit = 50) {
  const params = userId ? `?user_id=${userId}&limit=${limit}` : `?limit=${limit}`;
  return apiCall('GET', `/ledger${params}`);
}

// ─── Notifications ───────────────────────────────────

export async function sendTestNotification(userId, contactId) {
  return apiCall('POST', `/notifications/test/${userId}/${contactId}`);
}

export async function sendGuardianNotifications(userId) {
  return apiCall('POST', `/notifications/guardian/${userId}`);
}

export async function sendLockdownNotifications(userId) {
  return apiCall('POST', `/notifications/lockdown/${userId}`);
}

export async function getNotificationHistory(userId) {
  return apiCall('GET', `/notifications/${userId}`);
}

export async function getNotificationStatus() {
  return apiCall('GET', '/notifications/status');
}

export async function getSystemInfo() {
  return apiCall('GET', '/system/info');
}

// ─── Demo Controls ───────────────────────────────────

export async function simulateInactivity(seconds, userId) {
  return apiCall('POST', '/simulate/inactivity', { seconds, user_id: userId });
}

export async function simulateActivity(userId) {
  return apiCall('POST', `/simulate/activity?user_id=${userId || ''}`);
}

export async function resetSystem(userId) {
  return apiCall('POST', `/reset?user_id=${userId || ''}`);
}

// ─── WebSocket ────────────────────────────────────────

export function connectWebSocket(onMessage, onOpen, onClose) {
  if (_wsConnection && _wsConnection.readyState === WebSocket.OPEN) {
    return _wsConnection;
  }

  try {
    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      console.log('[WS] Connected to WillGuard backend');
      if (onOpen) onOpen();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (onMessage) onMessage(data);
      } catch (e) {
        console.warn('[WS] Failed to parse message:', e);
      }
    };

    ws.onclose = () => {
      console.log('[WS] Disconnected');
      _wsConnection = null;
      if (onClose) onClose();
      // Auto-reconnect after 5s
      _reconnectTimer = setTimeout(() => {
        connectWebSocket(onMessage, onOpen, onClose);
      }, 5000);
    };

    ws.onerror = (err) => {
      console.warn('[WS] Connection error');
      ws.close();
    };

    _wsConnection = ws;
    return ws;
  } catch (err) {
    console.warn('[WS] Could not connect');
    return null;
  }
}

export function disconnectWebSocket() {
  if (_reconnectTimer) clearTimeout(_reconnectTimer);
  if (_wsConnection) {
    _wsConnection.close();
    _wsConnection = null;
  }
}

// ─── Health Check ─────────────────────────────────────

export async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE}/status`, { method: 'GET' });
    return res.ok;
  } catch {
    return false;
  }
}
