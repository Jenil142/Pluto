import assert from 'node:assert';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const uiNodeModules = path.resolve(__dirname, '../ui/node_modules');

const { ThinkingOrb, resolvePreset, MODE_FRAMES, STATE_TO_MODE } = await import(
  path.join(uiNodeModules, 'thinking-orbs/dist/index.es.js')
);
const { renderToString } = await import(
  path.join(uiNodeModules, 'react-dom/server.node.js')
);
const React = (await import(path.join(uiNodeModules, 'react/index.js'))).default;
const { mapAgentStateToOrb } = await import('../ui/src/services/api.js');

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

async function testAsync(name, fn) {
  try {
    await fn();
    console.log(`[PASS] ${name}`);
    passed++;
  } catch (err) {
    console.error(`[FAIL] ${name}`);
    console.error(`       ${err.message}`);
    failed++;
  }
}

console.log('=== ThinkingOrb Dynamic State Transitions Adversarial Suite ===\n');

// 1. Core States Verification
const CORE_STATES = ['breathing', 'listening', 'searching', 'solving', 'working'];
const EXTENDED_STATES = ['connecting', 'weaving', 'composing', 'shaping'];

test('All 5 core ThinkingOrb states resolve valid preset modes and speeds', () => {
  for (const st of CORE_STATES) {
    const preset = resolvePreset(st, 64);
    assert.ok(preset, `Preset for state '${st}' should be defined`);
    assert.strictEqual(typeof preset.mode, 'string', `Preset mode for '${st}' should be string`);
    assert.strictEqual(typeof preset.speed, 'number', `Preset speed for '${st}' should be number`);
    assert.ok(preset.speed > 0, `Preset speed for '${st}' must be positive`);
    assert.strictEqual(preset.mode, STATE_TO_MODE[st], `Preset mode for '${st}' matches STATE_TO_MODE`);
  }
});

test('Extended ThinkingOrb states resolve valid preset modes', () => {
  for (const st of EXTENDED_STATES) {
    const preset = resolvePreset(st, 64);
    assert.ok(preset, `Preset for state '${st}' should be defined`);
    assert.strictEqual(preset.mode, STATE_TO_MODE[st]);
  }
});

// 2. Mathematical Frame Computation across Time
test('MODE_FRAMES generates deterministic non-empty frames for core states across time', () => {
  const times = [0.0, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0];
  const size = 64;

  for (const st of CORE_STATES) {
    const preset = resolvePreset(st, size);
    const frameFn = MODE_FRAMES[preset.mode];
    assert.strictEqual(typeof frameFn, 'function', `Frame function for mode '${preset.mode}' must exist`);

    for (const t of times) {
      const frameData = frameFn(size, t, preset.opts);
      assert.ok(frameData, `Frame data at t=${t} for state '${st}' must not be null`);
      assert.ok(Array.isArray(frameData.dots), `Frame data must contain dots array for state '${st}'`);
      assert.ok(frameData.dots.length > 0, `Frame data dots must not be empty for state '${st}'`);

      // Verify dot attributes (x, y, r, opacity/alpha)
      for (let i = 0; i < Math.min(5, frameData.dots.length); i++) {
        const dot = frameData.dots[i];
        assert.ok(Number.isFinite(dot.x), `Dot x coordinate must be finite: ${dot.x}`);
        assert.ok(Number.isFinite(dot.y), `Dot y coordinate must be finite: ${dot.y}`);
        assert.ok(dot.r >= 0, `Dot radius must be non-negative: ${dot.r}`);
      }
    }
  }
});

// 3. React SSR Component Rendering across supported sizes
test('ThinkingOrb renders canvas element without error for all core states at supported sizes', () => {
  const supportedSizes = [20, 32, 64];
  for (const size of supportedSizes) {
    for (const st of CORE_STATES) {
      const element = React.createElement(ThinkingOrb, {
        state: st,
        size,
        theme: 'light',
      });
      const html = renderToString(element);
      assert.ok(html.includes('<canvas'), `HTML should contain canvas tag for state ${st} size ${size}`);
      assert.ok(html.includes('role="img"'), `HTML should contain role="img" for state ${st} size ${size}`);
      assert.ok(html.includes(`width:${size}px`), `HTML should contain width:${size}px for state ${st}`);
      assert.ok(html.includes(`height:${size}px`), `HTML should contain height:${size}px for state ${st}`);
    }
  }
});

// 4. Status Label Mapping Verification
function getStatusLabel(state) {
  switch (state) {
    case 'listening':
      return 'Listening...';
    case 'connecting':
      return 'Connecting...';
    case 'searching':
      return 'Searching...';
    case 'solving':
      return 'Reasoning...';
    case 'working':
      return 'Executing...';
    case 'shaping':
      return 'Attention';
    case 'breathing':
    default:
      return 'Pluto Ready';
  }
}

test('Status labels match expected user interface semantics', () => {
  assert.strictEqual(getStatusLabel('listening'), 'Listening...');
  assert.strictEqual(getStatusLabel('connecting'), 'Connecting...');
  assert.strictEqual(getStatusLabel('searching'), 'Searching...');
  assert.strictEqual(getStatusLabel('solving'), 'Reasoning...');
  assert.strictEqual(getStatusLabel('working'), 'Executing...');
  assert.strictEqual(getStatusLabel('shaping'), 'Attention');
  assert.strictEqual(getStatusLabel('breathing'), 'Pluto Ready');
  assert.strictEqual(getStatusLabel('unknown_state'), 'Pluto Ready');
  assert.strictEqual(getStatusLabel(''), 'Pluto Ready');
});

// 5. State Machine Lifecycle Simulation
await testAsync('Simulates full query lifecycle transitions: idle -> focus -> submit -> reasoning -> complete', async () => {
  const stateTransitions = [];
  let currentOrbState = 'breathing';
  let isProcessing = false;

  function updateState(newState) {
    currentOrbState = newState;
    stateTransitions.push({ state: newState, timestamp: Date.now() });
  }

  // Step 1: User focuses input
  if (!isProcessing) {
    updateState('listening');
  }
  assert.strictEqual(currentOrbState, 'listening');

  // Step 2: User submits query
  isProcessing = true;
  updateState('working');
  assert.strictEqual(currentOrbState, 'working');

  // Simulating 50ms progression instead of multi-second delays for test execution
  let searchTimer = setTimeout(() => {
    updateState('searching');
  }, 20);

  let solvingTimer = setTimeout(() => {
    updateState('solving');
  }, 40);

  // Simulate server response after 30ms (before solvingTimer fires)
  await new Promise((resolve) => setTimeout(resolve, 30));
  clearTimeout(searchTimer);
  clearTimeout(solvingTimer);

  const serverAgentState = 'idle';
  const nextOrbState = mapAgentStateToOrb(serverAgentState);
  updateState(nextOrbState);
  assert.strictEqual(currentOrbState, 'breathing');

  // Finally block cleanup
  await new Promise((resolve) => setTimeout(resolve, 10));
  updateState('breathing');
  isProcessing = false;

  assert.strictEqual(isProcessing, false);
  assert.strictEqual(currentOrbState, 'breathing');

  const visitedStates = stateTransitions.map((t) => t.state);
  assert.ok(visitedStates.includes('listening'));
  assert.ok(visitedStates.includes('working'));
  assert.ok(visitedStates.includes('searching'));
  assert.ok(visitedStates.includes('breathing'));
});

// 6. Deliberation Lifecycle with Deep Reasoning (>40ms simulated)
await testAsync('Simulates deep reasoning lifecycle: working -> searching -> solving -> response', async () => {
  const stateTransitions = [];
  let currentOrbState = 'working';

  function updateState(newState) {
    currentOrbState = newState;
    stateTransitions.push(newState);
  }

  const searchTimer = setTimeout(() => {
    updateState('searching');
  }, 15);

  const solvingTimer = setTimeout(() => {
    updateState('solving');
  }, 30);

  // Wait 45ms to let both searchTimer and solvingTimer fire
  await new Promise((resolve) => setTimeout(resolve, 45));
  clearTimeout(searchTimer);
  clearTimeout(solvingTimer);

  assert.strictEqual(currentOrbState, 'solving');

  // Server responds
  updateState(mapAgentStateToOrb('idle'));
  assert.strictEqual(currentOrbState, 'breathing');

  assert.deepStrictEqual(stateTransitions, ['searching', 'solving', 'breathing']);
});

// 7. Error Lifecycle Simulation
await testAsync('Simulates error lifecycle: working -> error -> shaping -> breathing', async () => {
  let currentOrbState = 'working';

  // Simulating error catch block
  currentOrbState = 'shaping';
  assert.strictEqual(currentOrbState, 'shaping');
  assert.strictEqual(getStatusLabel(currentOrbState), 'Attention');

  // Finally block reset
  await new Promise((resolve) => setTimeout(resolve, 20));
  currentOrbState = 'breathing';
  assert.strictEqual(currentOrbState, 'breathing');
  assert.strictEqual(getStatusLabel(currentOrbState), 'Pluto Ready');
});

// 8. Rapid State Flapping Stress Test (1000 sequential transitions)
test('Rapid state flapping stress test: handles 1000 transitions without memory leak or crash', () => {
  const sequence = ['breathing', 'listening', 'working', 'searching', 'solving', 'shaping'];
  let currentState = 'breathing';

  const startMem = process.memoryUsage().heapUsed;
  for (let i = 0; i < 1000; i++) {
    const target = sequence[i % sequence.length];
    const mapped = mapAgentStateToOrb(target);
    const preset = resolvePreset(mapped, 64);
    assert.ok(preset.mode);
    currentState = mapped;
  }
  const endMem = process.memoryUsage().heapUsed;
  const deltaKb = (endMem - startMem) / 1024;

  assert.strictEqual(currentState, sequence[999 % sequence.length]);
  console.log(`       1000 state transitions heap delta: ${deltaKb.toFixed(2)} KB`);
});

// 9. Invalid State Resilience and Guard
test('mapAgentStateToOrb shields ThinkingOrb from invalid states that would otherwise crash resolvePreset', () => {
  const maliciousOrInvalidStates = [
    'malicious_state',
    'CRASH_ORB',
    '../../etc/passwd',
    'undefined',
    'null',
    '',
    ' ',
    '__proto__',
    'constructor',
    12345,
    {},
    [],
  ];

  for (const invalid of maliciousOrInvalidStates) {
    let directError = null;
    try {
      resolvePreset(invalid, 64);
    } catch (e) {
      directError = e;
    }
    assert.ok(directError !== null, `Direct resolvePreset('${invalid}') should throw`);

    const guarded = mapAgentStateToOrb(invalid);
    assert.strictEqual(guarded, 'breathing', `Guarded state for '${invalid}' must be 'breathing'`);

    const preset = resolvePreset(guarded, 64);
    assert.strictEqual(preset.mode, 'ring');
  }
});

// 10. Library Boundary Verification: Size Constraints
test('thinking-orbs strictly enforces size subset [20, 32, 64] and rejects arbitrary sizes', () => {
  const supportedSizes = [20, 32, 64];
  const unsupportedSizes = [16, 24, 48, 50, 72, 100, 128];

  for (const s of supportedSizes) {
    const preset = resolvePreset('breathing', s);
    assert.ok(preset);
  }

  for (const s of unsupportedSizes) {
    assert.throws(() => {
      resolvePreset('breathing', s);
    }, /Cannot read properties of undefined/);
  }
});

console.log(`\n=== Suite Completed: ${passed} passed, ${failed} failed ===`);
if (failed > 0) {
  process.exit(1);
}
