import http from 'node:http';
import assert from 'node:assert';
import { sendChatMessage, checkBackendHealth, mapAgentStateToOrb } from '../ui/src/services/api.js';

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

async function run() {
  console.log('--- Starting UI Services & Resilience Stress Tests ---\n');

  // Test 1: mapAgentStateToOrb mapping
  await test('mapAgentStateToOrb maps all known and fallback states', () => {
    assert.strictEqual(mapAgentStateToOrb('listening'), 'listening');
    assert.strictEqual(mapAgentStateToOrb('searching'), 'searching');
    assert.strictEqual(mapAgentStateToOrb('solving'), 'solving');
    assert.strictEqual(mapAgentStateToOrb('working'), 'working');
    assert.strictEqual(mapAgentStateToOrb('connecting'), 'connecting');
    assert.strictEqual(mapAgentStateToOrb('error'), 'shaping');
    assert.strictEqual(mapAgentStateToOrb('idle'), 'breathing');
    assert.strictEqual(mapAgentStateToOrb('unknown_xyz'), 'breathing');
    assert.strictEqual(mapAgentStateToOrb(''), 'breathing');
    assert.strictEqual(mapAgentStateToOrb(null), 'breathing');
  });

  // Test 2: Input boundary validation in sendChatMessage
  await test('sendChatMessage rejects empty input', async () => {
    await assert.rejects(
      async () => await sendChatMessage(''),
      { message: 'Message cannot be empty.' }
    );
  });

  await test('sendChatMessage rejects whitespace-only input', async () => {
    await assert.rejects(
      async () => await sendChatMessage('   \n\t  '),
      { message: 'Message cannot be empty.' }
    );
  });

  await test('sendChatMessage rejects null/undefined input', async () => {
    await assert.rejects(
      async () => await sendChatMessage(null),
      { message: 'Message cannot be empty.' }
    );
    await assert.rejects(
      async () => await sendChatMessage(undefined),
      { message: 'Message cannot be empty.' }
    );
  });

  // Test 3: Offline backend connection refused
  await test('sendChatMessage fails gracefully when backend is offline', async () => {
    // Choose an unallocated high port
    const offlineUrl = 'http://127.0.0.1:59999';
    try {
      await sendChatMessage('Hello', offlineUrl);
      assert.fail('Should have thrown connection error');
    } catch (err) {
      assert.ok(err instanceof Error);
      assert.ok(err.message.length > 0);
    }
  });

  await test('checkBackendHealth fails gracefully when backend is offline', async () => {
    const offlineUrl = 'http://127.0.0.1:59999';
    try {
      await checkBackendHealth(offlineUrl);
      assert.fail('Should have thrown connection error');
    } catch (err) {
      assert.ok(err instanceof Error);
      assert.ok(err.message.length > 0);
    }
  });

  // Spin up a mock HTTP server to simulate backend behaviors
  let serverHandler = (req, res) => res.end('default');
  const server = http.createServer((req, res) => serverHandler(req, res));

  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  const mockUrl = `http://127.0.0.1:${port}`;

  try {
    // Test 4: Normal happy path
    await test('sendChatMessage handles 200 OK response correctly', async () => {
      serverHandler = (req, res) => {
        if (req.url === '/api/chat' && req.method === 'POST') {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ reply: 'All systems nominal.', state: 'idle' }));
        } else {
          res.writeHead(404);
          res.end();
        }
      };

      const result = await sendChatMessage('Status report', mockUrl);
      assert.strictEqual(result.reply, 'All systems nominal.');
      assert.strictEqual(result.state, 'idle');
    });

    // Test 5: checkBackendHealth 200 OK
    await test('checkBackendHealth handles 200 OK correctly', async () => {
      serverHandler = (req, res) => {
        if (req.url === '/api/health' && req.method === 'GET') {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ status: 'ok', service: 'pluto-api' }));
        } else {
          res.writeHead(404);
          res.end();
        }
      };

      const result = await checkBackendHealth(mockUrl);
      assert.strictEqual(result.status, 'ok');
      assert.strictEqual(result.service, 'pluto-api');
    });

    // Test 6: Backend HTTP 500 with JSON detail
    await test('sendChatMessage extracts error detail from JSON 500 response', async () => {
      serverHandler = (req, res) => {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ detail: 'LLM inference pipeline crashed.' }));
      };

      await assert.rejects(
        async () => await sendChatMessage('Test error', mockUrl),
        (err) => {
          assert.strictEqual(err.message, 'LLM inference pipeline crashed.');
          return true;
        }
      );
    });

    // Test 7: Backend HTTP 500 with HTML error body
    await test('sendChatMessage handles non-JSON 500 gracefully', async () => {
      serverHandler = (req, res) => {
        res.writeHead(500, { 'Content-Type': 'text/html' });
        res.end('<html><body>500 Internal Server Error</body></html>');
      };

      await assert.rejects(
        async () => await sendChatMessage('Test error', mockUrl),
        (err) => {
          assert.strictEqual(err.message, 'Server responded with HTTP 500');
          return true;
        }
      );
    });

    // Test 8: Backend HTTP 422 with FastAPI validation error object
    await test('sendChatMessage serializes structured detail when detail is an object/array', async () => {
      serverHandler = (req, res) => {
        res.writeHead(422, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          detail: [{ loc: ['body', 'message'], msg: 'Field required', type: 'missing' }]
        }));
      };

      await assert.rejects(
        async () => await sendChatMessage('Bad body', mockUrl),
        (err) => {
          assert.ok(err.message.includes('Field required'));
          return true;
        }
      );
    });

    // Test 9: Extreme query string length (100,000 characters)
    await test('sendChatMessage handles 100,000 character prompt payload', async () => {
      const hugePrompt = 'A'.repeat(100000);
      let receivedBytes = 0;

      serverHandler = (req, res) => {
        let body = '';
        req.on('data', (chunk) => {
          body += chunk;
        });
        req.on('end', () => {
          receivedBytes = body.length;
          const parsed = JSON.parse(body);
          assert.strictEqual(parsed.message.length, 100000);
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ reply: 'Received large payload.', state: 'idle' }));
        });
      };

      const result = await sendChatMessage(hugePrompt, mockUrl);
      assert.strictEqual(result.reply, 'Received large payload.');
      assert.ok(receivedBytes > 100000);
    });

    // Test 10: Special characters, unicode, emojis, code snippets
    await test('sendChatMessage preserves special characters, emojis, and code', async () => {
      const complexText = '🚀 Special test: <script>alert("xss")</script> & "quotes" and \'apostrophe\'\n\tMulti-line \u0000 null-byte';
      let echoMessage = '';

      serverHandler = (req, res) => {
        let body = '';
        req.on('data', (chunk) => { body += chunk; });
        req.on('end', () => {
          const parsed = JSON.parse(body);
          echoMessage = parsed.message;
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ reply: `Echo: ${parsed.message}`, state: 'idle' }));
        });
      };

      const result = await sendChatMessage(complexText, mockUrl);
      assert.strictEqual(echoMessage, complexText.trim());
      assert.strictEqual(result.reply, `Echo: ${complexText.trim()}`);
    });

    // Test 11: Rapid concurrent requests (50 simultaneous submissions)
    await test('sendChatMessage handles 50 concurrent requests cleanly', async () => {
      serverHandler = (req, res) => {
        let body = '';
        req.on('data', (chunk) => { body += chunk; });
        req.on('end', () => {
          const parsed = JSON.parse(body);
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ reply: `Response to ${parsed.message}`, state: 'idle' }));
        });
      };

      const promises = Array.from({ length: 50 }, (_, i) =>
        sendChatMessage(`Prompt ${i}`, mockUrl)
      );

      const results = await Promise.all(promises);
      assert.strictEqual(results.length, 50);
      results.forEach((res, i) => {
        assert.strictEqual(res.reply, `Response to Prompt ${i}`);
      });
    });

    // Test 12: Trailing slashes in baseUrl
    await test('sendChatMessage normalizes baseUrl with trailing slashes', async () => {
      let requestedUrl = '';
      serverHandler = (req, res) => {
        requestedUrl = req.url;
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ reply: 'OK', state: 'idle' }));
      };

      await sendChatMessage('Test', `${mockUrl}///`);
      assert.strictEqual(requestedUrl, '/api/chat');
    });

  } finally {
    server.close();
  }

  console.log(`\n--- Test Summary: ${passed} passed, ${failed} failed ---`);
  if (failed > 0) {
    process.exit(1);
  }
}

run();
