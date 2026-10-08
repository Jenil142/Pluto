export const DEFAULT_BASE_URL = 'http://localhost:8000';

/**
 * Sends a chat message query to the Pluto backend API.
 * @param {string} message - User prompt text
 * @param {string} sessionId - The ID of the current chat session
 * @param {string} [baseUrl] - Backend base URL (default: http://localhost:8000)
 * @returns {Promise<{ reply: string, state: string }>}
 */
export async function sendChatMessage(message, sessionId = 'main', baseUrl = DEFAULT_BASE_URL, timeoutMs = 0) {
  const trimmed = message ? message.trim() : '';
  if (!trimmed) {
    throw new Error('Message cannot be empty.');
  }

  const endpoint = `${baseUrl.replace(/\/+$/, '')}/api/chat`;
  const controller = new AbortController();
  const timeoutId = timeoutMs && timeoutMs > 0 ? setTimeout(() => controller.abort(), timeoutMs) : null;

  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message: trimmed, session_id: sessionId }),
      signal: timeoutId ? controller.signal : undefined,
    });

    if (!response.ok) {
      let detail = `Server responded with HTTP ${response.status}`;
      try {
        const errorData = await response.json();
        if (errorData && errorData.detail) {
          detail = typeof errorData.detail === 'string'
            ? errorData.detail
            : JSON.stringify(errorData.detail);
        }
      } catch {
        // Use default status text if response is not JSON
      }
      throw new Error(detail);
    }

    return await response.json();
  } catch (err) {
    if (err.name === 'AbortError') {
      const sec = Math.round(timeoutMs / 1000);
      throw new Error(`Request processing exceeded client limit (${sec} seconds). Please verify backend logs.`);
    }
    if (err.message && err.message.includes('Failed to fetch')) {
      throw new Error(`Unable to reach Pluto backend at ${baseUrl}. Ensure api.py is running on port 8000.`);
    }
    throw err;
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
}

/**
 * Checks connectivity and health of the Pluto backend service.
 * @param {string} [baseUrl] - Backend base URL (default: http://localhost:8000)
 * @returns {Promise<{ status: string, service: string }>}
 */
export async function checkBackendHealth(baseUrl = DEFAULT_BASE_URL) {
  const endpoint = `${baseUrl.replace(/\/+$/, '')}/api/health`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5000);

  try {
    const response = await fetch(endpoint, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`Health check failed with HTTP ${response.status}`);
    }

    return await response.json();
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new Error('Health check timed out after 5 seconds.');
    }
    if (err.message && err.message.includes('Failed to fetch')) {
      throw new Error(`Backend unavailable at ${baseUrl}. Connection refused.`);
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Maps backend agent state or UI lifecycle state to a valid ThinkingOrb animation state.
 * Valid ThinkingOrb states: 'working' | 'searching' | 'solving' | 'listening' | 'connecting' | 'weaving' | 'composing' | 'breathing' | 'shaping'
 * @param {string} state - Raw state string
 * @returns {'working' | 'searching' | 'solving' | 'listening' | 'connecting' | 'weaving' | 'composing' | 'breathing' | 'shaping'}
 */
export function mapAgentStateToOrb(state) {
  switch (state) {
    case 'listening':
      return 'listening';
    case 'searching':
      return 'searching';
    case 'solving':
      return 'solving';
    case 'working':
      return 'working';
    case 'connecting':
      return 'connecting';
    case 'error':
      return 'shaping';
    case 'idle':
    default:
      return 'breathing';
  }
}
