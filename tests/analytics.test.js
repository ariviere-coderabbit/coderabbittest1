const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { test } = require('node:test');
const { runInNewContext } = require('node:vm');

const source = readFileSync(join(__dirname, '../vendor/analytics-sdk.js'), 'utf8');

for (const accepted of [true, false]) {
  test(`track returns ${accepted} when sendBeacon returns ${accepted}`, () => {
    const calls = [];
    const context = {
      navigator: {
        sendBeacon(url, body) {
          calls.push({ url, body });
          return accepted;
        }
      }
    };
    runInNewContext(source, context);
    context.Analytics.init({ session_id: 'test-session' });

    assert.equal(context.Analytics.track('purchase', { total: 0 }), accepted);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, 'https://analytics.example.com/collect');
    const payload = JSON.parse(calls[0].body);
    assert.equal(payload.session, 'test-session');
    assert.equal(payload.event, 'purchase');
    assert.deepEqual(payload.props, { total: 0 });
    assert.equal(Number.isFinite(payload.ts), true);
  });
}

test('track returns false when sendBeacon is unavailable', () => {
  const context = { navigator: {} };
  runInNewContext(source, context);
  assert.equal(context.Analytics.track('purchase', {}), false);
});
