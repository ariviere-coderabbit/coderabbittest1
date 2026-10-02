const assert = require('node:assert/strict');
const { test } = require('node:test');
const { generateBillingSummary, groupCyclesByPlan, detectAnomalies } = require('../src/billing.ts');

function cycle(overrides = {}) {
  return {
    cycleId: 'cycle-1', subscriptionId: 'subscription-1', userId: 'user-1',
    planId: 'basic', amount: 30, currency: 'USD', billingPeriodDays: 30,
    startDate: '2026-01-01', endDate: '2026-01-31', status: 'paid',
    ...overrides,
  };
}

test('empty input returns zero for every summary metric', () => {
  assert.deepEqual(generateBillingSummary([]), {
    totalRevenue: 0, successfulPayments: 0, failedPayments: 0,
    refundedAmount: 0, netRevenue: 0, mrr: 0, averageRevenuePerUser: 0,
  });
});

test('monthly revenue sums each paid cycle and ARPU counts distinct supplied users', () => {
  const summary = generateBillingSummary([
    cycle({ amount: 10 }),
    cycle({ amount: 20, billingPeriodDays: 60 }),
    cycle({ amount: 5, status: 'refunded' }),
    cycle({ status: 'failed', userId: 'user-2' }),
    cycle({ status: 'pending', userId: 'user-3' }),
  ]);
  assert.deepEqual(summary, {
    totalRevenue: 30, successfulPayments: 2, failedPayments: 1,
    refundedAmount: 5, netRevenue: 25, mrr: 20, averageRevenuePerUser: 10,
  });
});

test('summary rounds monthly revenue and ARPU to two decimals', () => {
  const summary = generateBillingSummary([
    cycle({ amount: 10, billingPeriodDays: 90 }),
    cycle({ status: 'pending', userId: 'user-2' }),
    cycle({ status: 'pending', userId: 'user-3' }),
  ]);
  assert.equal(summary.mrr, 3.33);
  assert.equal(summary.averageRevenuePerUser, 3.33);
});

test('no paid cycles produces zero MRR and ARPU, including refund-only input', () => {
  assert.deepEqual(generateBillingSummary([
    cycle({ status: 'failed', billingPeriodDays: 0 }),
    cycle({ status: 'refunded', amount: 12 }),
  ]), {
    totalRevenue: 0, successfulPayments: 0, failedPayments: 1,
    refundedAmount: 12, netRevenue: -12, mrr: 0, averageRevenuePerUser: 0,
  });
});

test('mixed paid and refund currencies are rejected before aggregation', () => {
  for (const status of ['paid', 'refunded']) {
    assert.throws(() => generateBillingSummary([
      cycle(), cycle({ currency: 'EUR', status }),
    ]), /single currency/);
  }
  assert.throws(() => generateBillingSummary([
    cycle({ status: 'refunded' }),
    cycle({ status: 'refunded', currency: 'EUR' }),
  ]), /single currency/);
});

test('non-revenue currencies do not affect the summary', () => {
  const summary = generateBillingSummary([
    cycle(), cycle({ status: 'failed', currency: 'EUR' }),
    cycle({ status: 'pending', currency: 'GBP' }),
  ]);
  assert.equal(summary.totalRevenue, 30);
  assert.equal(summary.netRevenue, 30);
  assert.equal(summary.mrr, 30);
});

test('invalid paid billing periods are rejected', () => {
  for (const billingPeriodDays of [0, -1, NaN, Infinity, -Infinity]) {
    assert.throws(() => generateBillingSummary([cycle({ billingPeriodDays })]), /positive/);
  }
});

test('plan groups support prototype property names and preserve order', () => {
  const cycles = ['constructor', '__proto__', 'toString', 'basic', '__proto__']
    .map((planId) => cycle({ planId }));
  const groups = groupCyclesByPlan(cycles);
  assert.equal(Object.getPrototypeOf(groups), null);
  assert.deepEqual(Object.keys(groups), ['constructor', '__proto__', 'toString', 'basic']);
  assert.deepEqual(groups.__proto__, [cycles[1], cycles[4]]);
  assert.deepEqual(groups.constructor, [cycles[0]]);
  assert.deepEqual(Object.keys(groupCyclesByPlan([])), []);
});

test('anomaly statistics and results include only paid cycles', () => {
  const outlier = cycle({ amount: 100 });
  const paid = [...Array.from({ length: 9 }, () => cycle({ amount: 10 })), outlier];
  const unpaid = ['failed', 'refunded', 'pending'].map((status) => cycle({ status, amount: -10000 }));
  assert.deepEqual(detectAnomalies([...paid, ...unpaid]), [outlier]);
  assert.deepEqual(detectAnomalies(paid), [outlier]);
  assert.deepEqual(detectAnomalies([cycle(), cycle()]), []);
});

test('fewer than two paid cycles cannot yield anomalies', () => {
  assert.deepEqual(detectAnomalies([]), []);
  assert.deepEqual(detectAnomalies([cycle({ status: 'failed' }), cycle({ status: 'refunded' })]), []);
  assert.deepEqual(detectAnomalies([cycle(), cycle({ status: 'failed', amount: 999 })]), []);
});
