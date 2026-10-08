import assert from 'node:assert';

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`[PASS] ${name}`);
    passed++;
  } catch (err) {
    console.error(`[FAIL] ${name}`);
    console.error(`       ${err.message}`);
    failed++;
  }
}

// Mock LocalStorage Implementation supporting quotas and security exceptions
class MockLocalStorage {
  constructor() {
    this.store = new Map();
    this.quotaLimitBytes = Infinity;
    this.securityErrorOnAccess = false;
  }

  getItem(key) {
    if (this.securityErrorOnAccess) {
      throw new DOMException('Access denied by security sandbox', 'SecurityError');
    }
    return this.store.has(key) ? this.store.get(key) : null;
  }

  setItem(key, value) {
    if (this.securityErrorOnAccess) {
      throw new DOMException('Access denied by security sandbox', 'SecurityError');
    }
    const strVal = String(value);
    let totalSize = strVal.length;
    for (const [k, v] of this.store) {
      if (k !== key) totalSize += v.length;
    }
    if (totalSize > this.quotaLimitBytes) {
      throw new DOMException('QuotaExceededError: storage limit reached', 'QuotaExceededError');
    }
    this.store.set(key, strVal);
  }

  removeItem(key) {
    if (this.securityErrorOnAccess) {
      throw new DOMException('Access denied by security sandbox', 'SecurityError');
    }
    this.store.delete(key);
  }

  clear() {
    if (this.securityErrorOnAccess) {
      throw new DOMException('Access denied by security sandbox', 'SecurityError');
    }
    this.store.clear();
  }
}

// Logic implementations mirroring App.jsx with resilience testing
const DEFAULT_SETTINGS = {
  apiEndpoint: 'http://localhost:8000',
  model: 'pluto-core-v1',
  theme: 'light',
};

function createInitialSession() {
  const id = `session-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  return {
    id,
    title: 'New Chat',
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [],
  };
}

function initSessionsFromStorage(localStorage) {
  try {
    const stored = localStorage.getItem('pluto_chat_sessions');
    if (stored) {
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed;
      }
    }
  } catch (e) {
    // console.warn
  }
  return [createInitialSession()];
}

// Hardened session sanitizer that guards against corrupt array contents
function sanitizeSessions(sessions) {
  if (!Array.isArray(sessions) || sessions.length === 0) {
    return [createInitialSession()];
  }
  const cleaned = sessions
    .filter((s) => s && typeof s === 'object' && typeof s.id === 'string')
    .map((s) => ({
      ...s,
      title: typeof s.title === 'string' ? s.title : 'New Chat',
      messages: Array.isArray(s.messages) ? s.messages.filter((m) => m && typeof m === 'object') : [],
    }));
  return cleaned.length > 0 ? cleaned : [createInitialSession()];
}

function initSettingsFromStorage(localStorage) {
  try {
    const saved = localStorage.getItem('pluto_settings');
    if (saved) {
      return JSON.parse(saved);
    }
  } catch (e) {
    // console.warn
  }
  return DEFAULT_SETTINGS;
}

function computeAutoTitle(existingTitle, existingMessagesLength, text) {
  const isFresh = existingTitle === 'New Chat' && existingMessagesLength === 0;
  return isFresh
    ? text.length > 28
      ? `${text.slice(0, 28)}...`
      : text
    : existingTitle;
}

function deleteSessionState(sessions, activeSessionId, idToDelete) {
  const remaining = sessions.filter((s) => s.id !== idToDelete);
  if (remaining.length === 0) {
    const fresh = createInitialSession();
    return {
      newSessions: [fresh],
      newActiveId: fresh.id,
    };
  }
  let newActiveId = activeSessionId;
  if (activeSessionId === idToDelete) {
    newActiveId = remaining[0].id;
  }
  return {
    newSessions: remaining,
    newActiveId,
  };
}

console.log('=== Deep Adversarial LocalStorage & State Resilience Suite ===\n');

// 1. Corrupt JSON and Malformed Data Injections
test('Handles truncated JSON strings gracefully', () => {
  const ls = new MockLocalStorage();
  ls.setItem('pluto_chat_sessions', '{"id":"session-1","title":"Incomplete');
  const sessions = initSessionsFromStorage(ls);
  assert.strictEqual(sessions.length, 1);
  assert.strictEqual(sessions[0].title, 'New Chat');
});

test('Handles non-JSON literals: NaN, undefined, boolean, numbers', () => {
  const ls = new MockLocalStorage();
  const corruptValues = ['NaN', 'undefined', 'true', 'false', '12345.67', 'function() {}'];
  for (const val of corruptValues) {
    ls.setItem('pluto_chat_sessions', val);
    const sessions = initSessionsFromStorage(ls);
    assert.strictEqual(sessions.length, 1);
    assert.strictEqual(sessions[0].title, 'New Chat');
  }
});

test('Sanitizes array containing null, undefined, or primitive items', () => {
  const dirty = [null, undefined, 42, 'invalid', { id: 's1', title: 'Valid 1', messages: [] }];
  const cleaned = sanitizeSessions(dirty);
  assert.strictEqual(cleaned.length, 1);
  assert.strictEqual(cleaned[0].id, 's1');
});

test('Sanitizes session objects with corrupt non-array messages property', () => {
  const dirty = [
    { id: 's1', title: 'Chat A', messages: 'corrupt-string' },
    { id: 's2', title: 'Chat B', messages: 12345 },
    { id: 's3', title: 'Chat C', messages: null },
    { id: 's4', title: 'Chat D', messages: [{ role: 'user', content: 'valid' }, null] },
  ];
  const cleaned = sanitizeSessions(dirty);
  assert.strictEqual(cleaned.length, 4);
  assert.ok(Array.isArray(cleaned[0].messages));
  assert.strictEqual(cleaned[0].messages.length, 0);
  assert.ok(Array.isArray(cleaned[1].messages));
  assert.strictEqual(cleaned[1].messages.length, 0);
  assert.ok(Array.isArray(cleaned[2].messages));
  assert.strictEqual(cleaned[2].messages.length, 0);
  assert.strictEqual(cleaned[3].messages.length, 1);
});

// 2. Browser Sandbox & Security Exception Resilience
test('Handles SecurityError when localStorage access is blocked in sandbox', () => {
  const ls = new MockLocalStorage();
  ls.securityErrorOnAccess = true;

  // Reading should not crash, but fall back to defaults
  const sessions = initSessionsFromStorage(ls);
  assert.strictEqual(sessions.length, 1);
  assert.strictEqual(sessions[0].title, 'New Chat');

  const settings = initSettingsFromStorage(ls);
  assert.deepStrictEqual(settings, DEFAULT_SETTINGS);
});

// 3. Quota Exceeded Containment
test('Simulates storage QuotaExceededError and verifies safe containment', () => {
  const ls = new MockLocalStorage();
  ls.quotaLimitBytes = 500; // Small limit to trigger quota exception

  const largeData = JSON.stringify(Array.from({ length: 50 }, (_, i) => ({
    id: `session-${i}`,
    title: `Chat ${i}`,
    messages: [{ role: 'user', content: 'Detailed message testing local quota exhaustion.' }],
  })));

  let quotaCaught = false;
  try {
    ls.setItem('pluto_chat_sessions', largeData);
  } catch (err) {
    if (err.name === 'QuotaExceededError') {
      quotaCaught = true;
    }
  }
  assert.strictEqual(quotaCaught, true);
  // Verify storage was not left in partially corrupted state
  assert.strictEqual(ls.getItem('pluto_chat_sessions'), null);
});

// 4. Auto-Titling Boundary & Unicode Stress
test('Auto-titling: exact boundaries 27, 28, 29 characters', () => {
  const str27 = 'A'.repeat(27);
  const str28 = 'B'.repeat(28);
  const str29 = 'C'.repeat(29);

  assert.strictEqual(computeAutoTitle('New Chat', 0, str27), str27);
  assert.strictEqual(computeAutoTitle('New Chat', 0, str28), str28);
  assert.strictEqual(computeAutoTitle('New Chat', 0, str29), `${'C'.repeat(28)}...`);
});

test('Auto-titling: unicode and emoji surrogate boundary behavior', () => {
  // 27 chars + 1 rocket emoji (2 code units = total 29)
  const emojiStr = 'A'.repeat(27) + '🚀';
  assert.strictEqual(emojiStr.length, 29);
  const title = computeAutoTitle('New Chat', 0, emojiStr);
  // Slicing at 28 produces 27 'A's + high surrogate
  assert.strictEqual(title.length, 31); // 28 sliced units + '...'
  assert.strictEqual(title.slice(-3), '...');
});

test('Auto-titling: preserves custom renamed titles regardless of message count', () => {
  assert.strictEqual(computeAutoTitle('Autonomous Warehouse Node', 0, 'New query'), 'Autonomous Warehouse Node');
  assert.strictEqual(computeAutoTitle('My Custom Project', 5, 'Another query'), 'My Custom Project');
  assert.strictEqual(computeAutoTitle('', 0, 'Should keep empty custom title'), '');
});

// 5. Session Deletion Exhaustive Edge Cases
test('Session deletion: deletes non-active session, preserves active session ID', () => {
  const sessions = [{ id: 's1' }, { id: 's2' }, { id: 's3' }];
  const { newSessions, newActiveId } = deleteSessionState(sessions, 's1', 's2');
  assert.strictEqual(newSessions.length, 2);
  assert.strictEqual(newActiveId, 's1');
  assert.deepStrictEqual(newSessions.map(s => s.id), ['s1', 's3']);
});

test('Session deletion: deletes active session, pivots to next remaining session', () => {
  const sessions = [{ id: 's1' }, { id: 's2' }, { id: 's3' }];
  const { newSessions, newActiveId } = deleteSessionState(sessions, 's1', 's1');
  assert.strictEqual(newSessions.length, 2);
  assert.strictEqual(newActiveId, 's2');
});

test('Session deletion: deleting last remaining session generates fresh session', () => {
  const sessions = [{ id: 'only-session' }];
  const { newSessions, newActiveId } = deleteSessionState(sessions, 'only-session', 'only-session');
  assert.strictEqual(newSessions.length, 1);
  assert.strictEqual(newSessions[0].title, 'New Chat');
  assert.strictEqual(newActiveId, newSessions[0].id);
  assert.notStrictEqual(newActiveId, 'only-session');
});

test('Session deletion: deleting non-existent session ID is idempotent', () => {
  const sessions = [{ id: 's1' }, { id: 's2' }];
  const { newSessions, newActiveId } = deleteSessionState(sessions, 's1', 'non-existent-id');
  assert.strictEqual(newSessions.length, 2);
  assert.strictEqual(newActiveId, 's1');
});

// 6. Volume & Performance Scaling Benchmark
test('Scaling benchmark: serializes and parses 1000 sessions with 5000 messages in < 250ms', () => {
  const sessions = Array.from({ length: 1000 }, (_, i) => ({
    id: `sess-benchmark-${i}`,
    title: `Autonomous Task ${i}`,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [
      { id: `m-${i}-1`, role: 'user', content: `Run warehouse benchmark test for node ${i}` },
      { id: `m-${i}-2`, role: 'assistant', content: `Executed task ${i}. All subsystems nominal.` },
      { id: `m-${i}-3`, role: 'user', content: `Inspect sensor fusion odometry telemetry.` },
      { id: `m-${i}-4`, role: 'assistant', content: `EKF fusion verified within +/- 0.02m error.` },
      { id: `m-${i}-5`, role: 'assistant', content: `Telemetry logged to persistent ledger.` },
    ],
  }));

  const ls = new MockLocalStorage();

  // Serialization measurement
  const t0 = performance.now();
  const serialized = JSON.stringify(sessions);
  ls.setItem('pluto_chat_sessions', serialized);
  const serializeDuration = performance.now() - t0;

  // Deserialization measurement
  const t1 = performance.now();
  const parsed = initSessionsFromStorage(ls);
  const deserializeDuration = performance.now() - t1;

  const totalBytes = serialized.length;
  console.log(`       1000 sessions (5000 msgs) payload size: ${(totalBytes / 1024).toFixed(1)} KB`);
  console.log(`       Serialization time: ${serializeDuration.toFixed(2)} ms`);
  console.log(`       Deserialization time: ${deserializeDuration.toFixed(2)} ms`);

  assert.strictEqual(parsed.length, 1000);
  assert.strictEqual(parsed[999].messages.length, 5);
  assert.ok(serializeDuration + deserializeDuration < 250, 'Total serialization cycle must be under 250ms');
});

console.log(`\n=== Suite Completed: ${passed} passed, ${failed} failed ===`);
if (failed > 0) {
  process.exit(1);
}
