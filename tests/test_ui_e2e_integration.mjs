import { spawn } from 'node:child_process';
import assert from 'node:assert';
import { sendChatMessage, checkBackendHealth } from '../ui/src/services/api.js';

let passed = 0;
let failed = 0;

async function test(name, fn) {
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

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForServer(url, timeoutMs = 10000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await checkBackendHealth(url);
      if (res && res.status === 'ok') return true;
    } catch {
      await sleep(200);
    }
  }
  return false;
}

async function run() {
  console.log('--- Starting Live E2E Integration Stress Tests (Frontend API <-> Live api.py) ---\n');

  const backendUrl = 'http://127.0.0.1:8000';
  const offlineUrl = 'http://127.0.0.1:59999';

  // 1. First test: Confirm offline handling when server is NOT running
  await test('sendChatMessage fails gracefully when server is offline', async () => {
    await assert.rejects(
      async () => await sendChatMessage('Hello', offlineUrl),
      (err) => {
        assert.ok(err instanceof Error);
        return true;
      }
    );
  });

  // 2. Start Uvicorn process if not already running on port 8000
  let serverProc = null;
  const isAlreadyLive = await waitForServer(backendUrl, 1000);
  if (!isAlreadyLive) {
    console.log('Spawning live uvicorn api:app on port 8000...');
    serverProc = spawn('./.venv/bin/python', ['-m', 'uvicorn', 'api:app', '--host', '127.0.0.1', '--port', '8000'], {
      cwd: '/home/jenil/Pluto',
      stdio: 'ignore',
      detached: true,
    });
  } else {
    console.log('Detected active uvicorn server already running on port 8000.');
  }

  try {
    const ready = isAlreadyLive || await waitForServer(backendUrl, 10000);
    assert.ok(ready, 'FastAPI server failed to become ready within 10 seconds');
    console.log('FastAPI server is live and healthy on port 8000!\n');

    // Test 3: checkBackendHealth against live server
    await test('Live checkBackendHealth returns ok status and pluto-api service', async () => {
      const res = await checkBackendHealth(backendUrl);
      assert.strictEqual(res.status, 'ok');
      assert.strictEqual(res.service, 'pluto-api');
    });

    // Test 4: Live sendChatMessage with standard greeting
    await test('Live sendChatMessage processes greeting successfully', async () => {
      const res = await sendChatMessage('Hello Pluto', backendUrl);
      assert.ok(typeof res.reply === 'string' && res.reply.length > 0);
      assert.strictEqual(res.state, 'idle');
      console.log(`       Live reply snippet: "${res.reply.slice(0, 60)}..."`);
    });

    // Test 5: Live sendChatMessage with status query
    await test('Live sendChatMessage answers status query', async () => {
      const res = await sendChatMessage('status check', backendUrl);
      assert.ok(typeof res.reply === 'string' && res.reply.length > 0);
      assert.strictEqual(res.state, 'idle');
    });

    // Test 6: Live sendChatMessage with starter chip queries
    const starters = [
      'Check system status',
      'Explain Pluto perception-action pipeline',
      'Design an autonomous warehouse navigation node',
    ];
    for (const starter of starters) {
      await test(`Live sendChatMessage handles starter prompt: "${starter}"`, async () => {
        const res = await sendChatMessage(starter, backendUrl);
        assert.ok(typeof res.reply === 'string' && res.reply.length > 0);
        assert.strictEqual(res.state, 'idle');
      });
    }

    // Test 7: Live sendChatMessage with 5,000 character long prompt
    await test('Live sendChatMessage handles 5,000 character prompt', async () => {
      const longPrompt = 'Describe warehouse robotics '.repeat(170); // ~4930 chars
      const res = await sendChatMessage(longPrompt, backendUrl);
      assert.ok(typeof res.reply === 'string' && res.reply.length > 0);
    });

    // Test 8: Live sendChatMessage handles concurrent requests
    await test('Live sendChatMessage handles 5 concurrent requests', async () => {
      const queries = ['Query A', 'Query B', 'Query C', 'Query D', 'Query E'];
      const responses = await Promise.all(
        queries.map((q) => sendChatMessage(q, backendUrl))
      );
      assert.strictEqual(responses.length, 5);
      responses.forEach((r) => {
        assert.ok(typeof r.reply === 'string' && r.reply.length > 0);
      });
    });

  } finally {
    if (serverProc) {
      console.log('\nShutting down live uvicorn process...');
      try {
        process.kill(-serverProc.pid, 'SIGTERM');
      } catch {
        try {
          serverProc.kill('SIGTERM');
        } catch {
          // ignored
        }
      }
      await sleep(800);
    }
  }

  // Test 9: Verify offline resilience after server shutdown
  await test('sendChatMessage fails gracefully after server shutdown', async () => {
    await assert.rejects(
      async () => await sendChatMessage('Post shutdown test', offlineUrl),
      (err) => {
        assert.ok(err instanceof Error);
        return true;
      }
    );
  });

  console.log(`\n--- Live E2E Summary: ${passed} passed, ${failed} failed ---`);
  if (failed > 0) {
    process.exit(1);
  }
}

run();
