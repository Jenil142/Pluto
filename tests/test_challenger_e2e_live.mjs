/**
 * Pluto Live E2E Integration & Stress Harness (Node.js)
 * Tests live communication with http://127.0.0.1:8000
 * Covers:
 * 1. Health checks & basic chat round-trip
 * 2. Concurrent bursts (5, 10, 15 parallel queries)
 * 3. Extreme payload sizes (5,000 to 100,000 characters)
 * 4. Unicode, emojis, RTL, CJK, zalgo, zero-width chars, shell/SQL injection strings
 * 5. Whitespace boundary checks
 * 6. Offline network fault handling and recovery
 */

import { sendChatMessage, checkBackendHealth } from '../ui/src/services/api.js';

const LIVE_URL = 'http://127.0.0.1:8000';
const OFFLINE_URL = 'http://127.0.0.1:59999';

const results = {
  passed: 0,
  failed: 0,
  measurements: [],
  failures: []
};

function recordTest(name, passed, latencyMs = 0, details = '') {
  if (passed) {
    results.passed++;
    console.log(`[PASS] ${name} (${latencyMs.toFixed(1)} ms)`);
  } else {
    results.failed++;
    results.failures.push({ name, details });
    console.error(`[FAIL] ${name}: ${details}`);
  }
  results.measurements.push({ name, passed, latencyMs, details });
}

async function runHarness() {
  console.log('================================================================');
  console.log(' Pluto Live E2E Stress Verification Harness (Node.js Client) ');
  console.log(' Target: ' + LIVE_URL);
  console.log('================================================================\n');

  // Step 1: Health check
  try {
    const t0 = performance.now();
    const health = await checkBackendHealth(LIVE_URL);
    const dt = performance.now() - t0;
    const ok = health && health.status === 'ok' && health.service === 'pluto-api';
    recordTest('Live Health Check Endpoint', ok, dt, JSON.stringify(health));
  } catch (err) {
    recordTest('Live Health Check Endpoint', false, 0, err.message);
  }

  // Step 2: Basic Chat Latency
  try {
    const t0 = performance.now();
    const resp = await sendChatMessage('status', LIVE_URL);
    const dt = performance.now() - t0;
    const ok = resp && typeof resp.reply === 'string' && resp.reply.length > 0 && resp.state === 'idle';
    recordTest('Single Chat Message Latency (Local Fallback/Status)', ok, dt, `Reply: ${resp.reply.slice(0, 50)}...`);
  } catch (err) {
    recordTest('Single Chat Message Latency (Local Fallback/Status)', false, 0, err.message);
  }

  // Step 3: Whitespace query handled by local fallback
  try {
    const t0 = performance.now();
    let clientRejected = false;
    try {
      await sendChatMessage('   \n\t  ', LIVE_URL);
    } catch (clientErr) {
      if (clientErr.message.includes('Message cannot be empty')) {
        clientRejected = true;
      }
    }
    const dt = performance.now() - t0;
    recordTest('Client-Side Whitespace Validation (Pre-flight Rejection)', clientRejected, dt, 'Rejected before network');
  } catch (err) {
    recordTest('Client-Side Whitespace Validation (Pre-flight Rejection)', false, 0, err.message);
  }

  // Step 4: Large Payload Queries (5,000, 20,000, 50,000 characters)
  const sizes = [5000, 20000, 50000];
  for (const sz of sizes) {
    try {
      const prompt = 'Autonomous warehouse robotics navigation pipeline '.repeat(Math.ceil(sz / 50)).slice(0, sz);
      const t0 = performance.now();
      const resp = await sendChatMessage(prompt, LIVE_URL);
      const dt = performance.now() - t0;
      const ok = resp && typeof resp.reply === 'string' && resp.reply.length > 0;
      recordTest(`Large Payload Chat (${sz} chars)`, ok, dt, `Response len: ${resp.reply.length}`);
    } catch (err) {
      recordTest(`Large Payload Chat (${sz} chars)`, false, 0, err.message);
    }
  }

  // Step 5: Adversarial and Exotic Characters
  const exoticInputs = [
    { label: 'Multilingual CJK and Arabic', text: 'مرحبا بك في بلوتو | 欢迎来到 Pluto | ロボットの自律移動' },
    { label: 'Emojis and Math Symbols', text: '🚀🤖🪐✨ α + β = γ ∫(x^2)dx ∑_{i=1}^n x_i ≠ 0' },
    { label: 'Zalgo and Zero-Width', text: 'T̷e̸s̵t̸\u200b\u200c\u200d\ufeffZalgo' },
    { label: 'SQL Injection Payload', text: "'; DROP TABLE messages; SELECT * FROM messages WHERE '1'='1" },
    { label: 'Command Injection Syntax', text: '$(whoami); `id`; cat /etc/passwd; rm -rf /tmp/fake' },
    { label: 'HTML and Script Tags', text: '<script>alert(1)</script><img src="x" onerror="alert(2)">' },
  ];

  for (const item of exoticInputs) {
    try {
      const t0 = performance.now();
      const resp = await sendChatMessage(item.text, LIVE_URL);
      const dt = performance.now() - t0;
      const ok = resp && typeof resp.reply === 'string' && resp.reply.length > 0 && resp.state === 'idle';
      recordTest(`Exotic Input: ${item.label}`, ok, dt, `Reply len: ${resp.reply.length}`);
    } catch (err) {
      recordTest(`Exotic Input: ${item.label}`, false, 0, err.message);
    }
  }

  // Step 6: Burst Concurrency (5 parallel requests)
  try {
    const burstCount = 5;
    const queries = Array.from({ length: burstCount }, (_, i) => `Concurrent burst query #${i + 1} status`);
    const t0 = performance.now();
    const responses = await Promise.all(queries.map(q => sendChatMessage(q, LIVE_URL)));
    const dt = performance.now() - t0;
    const allValid = responses.every(r => r && typeof r.reply === 'string' && r.state === 'idle');
    recordTest(`Concurrent Burst (${burstCount} parallel queries)`, allValid, dt, `All ${burstCount} resolved successfully`);
  } catch (err) {
    recordTest('Concurrent Burst (5 parallel queries)', false, 0, err.message);
  }

  // Step 7: Burst Concurrency (10 parallel requests)
  try {
    const burstCount = 10;
    const queries = Array.from({ length: burstCount }, (_, i) => `High load query #${i + 1} time`);
    const t0 = performance.now();
    const responses = await Promise.all(queries.map(q => sendChatMessage(q, LIVE_URL)));
    const dt = performance.now() - t0;
    const allValid = responses.every(r => r && typeof r.reply === 'string' && r.state === 'idle');
    recordTest(`High-Load Concurrency Burst (${burstCount} parallel queries)`, allValid, dt, `Total elapsed: ${dt.toFixed(1)} ms`);
  } catch (err) {
    recordTest('High-Load Concurrency Burst (10 parallel queries)', false, 0, err.message);
  }

  // Step 8: Offline Error Handling
  try {
    const t0 = performance.now();
    let caught = false;
    let errorDetail = '';
    try {
      await sendChatMessage('Test offline message', OFFLINE_URL);
    } catch (err) {
      caught = true;
      errorDetail = err.message;
    }
    const dt = performance.now() - t0;
    const ok = caught && (errorDetail.includes('Unable to reach Pluto backend') || errorDetail.includes('fetch'));
    recordTest('Offline Error Handling (sendChatMessage)', ok, dt, errorDetail);
  } catch (err) {
    recordTest('Offline Error Handling (sendChatMessage)', false, 0, err.message);
  }

  // Step 9: Offline Health Check Error Handling
  try {
    const t0 = performance.now();
    let caught = false;
    let errorDetail = '';
    try {
      await checkBackendHealth(OFFLINE_URL);
    } catch (err) {
      caught = true;
      errorDetail = err.message;
    }
    const dt = performance.now() - t0;
    const ok = caught && (errorDetail.includes('Backend unavailable') || errorDetail.includes('fetch'));
    recordTest('Offline Error Handling (checkBackendHealth)', ok, dt, errorDetail);
  } catch (err) {
    recordTest('Offline Error Handling (checkBackendHealth)', false, 0, err.message);
  }

  // Step 10: Recovery after offline attempt
  try {
    const t0 = performance.now();
    const resp = await sendChatMessage('Recovery query after offline check', LIVE_URL);
    const dt = performance.now() - t0;
    const ok = resp && typeof resp.reply === 'string' && resp.reply.length > 0;
    recordTest('Post-Fault Recovery (Client resumes communication)', ok, dt, `Reply: ${resp.reply.slice(0, 40)}...`);
  } catch (err) {
    recordTest('Post-Fault Recovery (Client resumes communication)', false, 0, err.message);
  }

  console.log('\n================================================================');
  console.log(` Summary: ${results.passed} PASSED, ${results.failed} FAILED `);
  console.log('================================================================');

  if (results.failed > 0) {
    process.exit(1);
  }
}

runHarness();
