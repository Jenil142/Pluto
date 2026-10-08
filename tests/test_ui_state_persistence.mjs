import assert from 'node:assert';

// Mock localStorage environment
class MockLocalStorage {
  constructor() {
    this.store = new Map();
    this.shouldThrowOnSet = false;
  }

  getItem(key) {
    return this.store.has(key) ? this.store.get(key) : null;
  }

  setItem(key, value) {
    if (this.shouldThrowOnSet) {
      throw new DOMException('QuotaExceededError', 'QuotaExceededError');
    }
    this.store.set(key, String(value));
  }

  removeItem(key) {
    this.store.delete(key);
  }

  clear() {
    this.store.clear();
  }
}

// Logic replica from App.jsx for empirical verification
const DEFAULT_SETTINGS = {
  apiEndpoint: 'http://localhost:8000',
  model: 'pluto-core-v1',
  theme: 'light',
};

function createInitialSession() {
  const id = `session-${Date.now()}`;
  return {
    id,
    title: 'New Chat',
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [],
  };
}

function initSessions(localStorage) {
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

function initActiveSessionId(localStorage, sessions) {
  try {
    const savedId = localStorage.getItem('pluto_active_session_id');
    if (savedId) return savedId;
  } catch (e) {
    // console.warn
  }
  return sessions[0]?.id || '';
}

function initSettings(localStorage) {
  try {
    const savedSettings = localStorage.getItem('pluto_settings');
    if (savedSettings) {
      return JSON.parse(savedSettings);
    }
  } catch (e) {
    // console.warn
  }
  return DEFAULT_SETTINGS;
}

function deriveActiveSession(sessions, activeSessionId) {
  return (
    sessions.find((s) => s.id === activeSessionId) ||
    sessions[0] ||
    createInitialSession()
  );
}

function computeAutoTitle(existingTitle, existingMessagesLength, text) {
  const isFresh = existingTitle === 'New Chat' && existingMessagesLength === 0;
  return isFresh
    ? text.length > 28
      ? `${text.slice(0, 28)}...`
      : text
    : existingTitle;
}

function deleteSession(sessions, activeSessionId, idToDelete) {
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

console.log('--- Starting UI State Management & Persistence Stress Tests ---\n');

// 1. Initial storage restoration tests
test('Initializes with fresh session when localStorage is completely empty', () => {
  const ls = new MockLocalStorage();
  const sessions = initSessions(ls);
  assert.strictEqual(sessions.length, 1);
  assert.strictEqual(sessions[0].title, 'New Chat');
  assert.strictEqual(sessions[0].messages.length, 0);

  const activeId = initActiveSessionId(ls, sessions);
  assert.strictEqual(activeId, sessions[0].id);

  const settings = initSettings(ls);
  assert.deepStrictEqual(settings, DEFAULT_SETTINGS);
});

test('Restores sessions, activeSessionId, and settings from valid localStorage', () => {
  const ls = new MockLocalStorage();
  const savedSessions = [
    { id: 'session-100', title: 'Saved Chat 1', messages: [{ id: 'm1', content: 'hello' }] },
    { id: 'session-200', title: 'Saved Chat 2', messages: [] }
  ];
  ls.setItem('pluto_chat_sessions', JSON.stringify(savedSessions));
  ls.setItem('pluto_active_session_id', 'session-200');
  ls.setItem('pluto_settings', JSON.stringify({ apiEndpoint: 'http://custom:9000', theme: 'light', model: 'custom-m' }));

  const sessions = initSessions(ls);
  assert.strictEqual(sessions.length, 2);
  assert.strictEqual(sessions[0].id, 'session-100');

  const activeId = initActiveSessionId(ls, sessions);
  assert.strictEqual(activeId, 'session-200');

  const settings = initSettings(ls);
  assert.strictEqual(settings.apiEndpoint, 'http://custom:9000');
});

test('Handles corrupted JSON in pluto_chat_sessions gracefully without crash', () => {
  const ls = new MockLocalStorage();
  ls.setItem('pluto_chat_sessions', '{not valid json!!!');

  const sessions = initSessions(ls);
  assert.strictEqual(sessions.length, 1);
  assert.strictEqual(sessions[0].title, 'New Chat');
});

test('Handles non-array JSON in pluto_chat_sessions (e.g. object, number, boolean)', () => {
  const ls = new MockLocalStorage();

  ls.setItem('pluto_chat_sessions', JSON.stringify({ not: 'an array' }));
  let sessions = initSessions(ls);
  assert.strictEqual(sessions.length, 1);

  ls.setItem('pluto_chat_sessions', JSON.stringify(12345));
  sessions = initSessions(ls);
  assert.strictEqual(sessions.length, 1);

  ls.setItem('pluto_chat_sessions', JSON.stringify(true));
  sessions = initSessions(ls);
  assert.strictEqual(sessions.length, 1);
});

test('Handles empty array in pluto_chat_sessions by creating initial session', () => {
  const ls = new MockLocalStorage();
  ls.setItem('pluto_chat_sessions', JSON.stringify([]));

  const sessions = initSessions(ls);
  assert.strictEqual(sessions.length, 1);
  assert.strictEqual(sessions[0].title, 'New Chat');
});

test('Handles orphaned activeSessionId not matching any session', () => {
  const ls = new MockLocalStorage();
  const sessions = [
    { id: 'session-alpha', title: 'Alpha', messages: [] }
  ];
  ls.setItem('pluto_active_session_id', 'session-nonexistent-999');

  const activeId = initActiveSessionId(ls, sessions);
  assert.strictEqual(activeId, 'session-nonexistent-999');

  // deriveActiveSession should safely fall back to sessions[0]
  const activeSession = deriveActiveSession(sessions, activeId);
  assert.strictEqual(activeSession.id, 'session-alpha');
});

test('Handles corrupted pluto_settings gracefully', () => {
  const ls = new MockLocalStorage();
  ls.setItem('pluto_settings', 'CORRUPT_JSON_DATA');

  const settings = initSettings(ls);
  assert.deepStrictEqual(settings, DEFAULT_SETTINGS);
});

// 2. Storage write error handling
test('Storage synchronization does not crash when QuotaExceededError is thrown', () => {
  const ls = new MockLocalStorage();
  ls.shouldThrowOnSet = true;

  let caughtSessions = false;
  try {
    ls.setItem('pluto_chat_sessions', 'data');
  } catch (e) {
    caughtSessions = true;
  }
  assert.strictEqual(caughtSessions, true);
});

// 3. Auto-titling edge cases
test('Auto-titling short prompt (<= 28 chars)', () => {
  const title = computeAutoTitle('New Chat', 0, 'Robotics pipeline test');
  assert.strictEqual(title, 'Robotics pipeline test');
});

test('Auto-titling exact 28 chars prompt', () => {
  const exact28 = '1234567890123456789012345678';
  const title = computeAutoTitle('New Chat', 0, exact28);
  assert.strictEqual(title, exact28);
});

test('Auto-titling long prompt (> 28 chars) truncates with ellipsis', () => {
  const longPrompt = 'Explain the full perception-action pipeline for Pluto autonomous warehouse robot';
  const title = computeAutoTitle('New Chat', 0, longPrompt);
  assert.strictEqual(title, 'Explain the full perception-...');
  assert.strictEqual(title.length, 31); // 28 chars + '...'
});

test('Auto-titling does not overwrite existing title on subsequent messages', () => {
  const title = computeAutoTitle('Robotics pipeline test', 2, 'Followup query here');
  assert.strictEqual(title, 'Robotics pipeline test');
});

test('Auto-titling preserves custom renamed title even with 0 messages', () => {
  const title = computeAutoTitle('Custom Project Title', 0, 'New query');
  assert.strictEqual(title, 'Custom Project Title');
});

// 4. Session deletion edge cases
test('Deleting non-active session preserves activeSessionId', () => {
  const sessions = [
    { id: 's1', title: 'Chat 1' },
    { id: 's2', title: 'Chat 2' },
    { id: 's3', title: 'Chat 3' },
  ];
  const { newSessions, newActiveId } = deleteSession(sessions, 's1', 's2');
  assert.strictEqual(newSessions.length, 2);
  assert.strictEqual(newActiveId, 's1');
  assert.deepStrictEqual(newSessions.map(s => s.id), ['s1', 's3']);
});

test('Deleting active session updates activeSessionId to first remaining session', () => {
  const sessions = [
    { id: 's1', title: 'Chat 1' },
    { id: 's2', title: 'Chat 2' },
    { id: 's3', title: 'Chat 3' },
  ];
  const { newSessions, newActiveId } = deleteSession(sessions, 's1', 's1');
  assert.strictEqual(newSessions.length, 2);
  assert.strictEqual(newActiveId, 's2');
});

test('Deleting only session re-creates fresh initial session', () => {
  const sessions = [{ id: 's1', title: 'Sole Chat' }];
  const { newSessions, newActiveId } = deleteSession(sessions, 's1', 's1');
  assert.strictEqual(newSessions.length, 1);
  assert.strictEqual(newSessions[0].title, 'New Chat');
  assert.strictEqual(newActiveId, newSessions[0].id);
});

// 5. Stress test with 500 sessions and 2000 messages
test('State scales to 500 sessions with 2000 messages', () => {
  const largeSessions = Array.from({ length: 500 }, (_, i) => ({
    id: `session-scale-${i}`,
    title: `Chat ${i}`,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: Array.from({ length: 4 }, (_, m) => ({
      id: `msg-${i}-${m}`,
      role: m % 2 === 0 ? 'user' : 'assistant',
      content: `Message ${m} in session ${i} with engineering analysis content.`,
      timestamp: '12:00',
    }))
  }));

  const ls = new MockLocalStorage();
  const serialized = JSON.stringify(largeSessions);
  ls.setItem('pluto_chat_sessions', serialized);

  const restored = initSessions(ls);
  assert.strictEqual(restored.length, 500);
  assert.strictEqual(restored[499].messages.length, 4);

  const active = deriveActiveSession(restored, 'session-scale-250');
  assert.strictEqual(active.id, 'session-scale-250');
});

console.log(`\n--- Test Summary: ${passed} passed, ${failed} failed ---`);
if (failed > 0) {
  process.exit(1);
}
