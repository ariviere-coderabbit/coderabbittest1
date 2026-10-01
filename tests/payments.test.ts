import { calculateProRatedRefund, applyDiscount } from '../src/payments';

describe('calculateProRatedRefund', () => {
  it('returns a refund amount for partial use', () => {
    const result = calculateProRatedRefund({ totalPaid: 90, daysUsed: 10, totalDays: 30 });
    expect(result).toBe(60);
  });

  it('returns nothing when subscription is fully used', () => {
    const result = calculateProRatedRefund({ totalPaid: 90, daysUsed: 30, totalDays: 30 });
    expect(result).toBe(0);
  });

  it('throws when totalDays is zero', () => {
    expect(() => calculateProRatedRefund({ totalPaid: 90, daysUsed: 0, totalDays: 0 })).toThrow();
  });

  it('throws when totalDays is negative', () => {
    expect(() => calculateProRatedRefund({ totalPaid: 90, daysUsed: 0, totalDays: -1 })).toThrow();
  });

  it('throws when daysUsed exceeds totalDays', () => {
    expect(() => calculateProRatedRefund({ totalPaid: 90, daysUsed: 31, totalDays: 30 })).toThrow();
  });
});

describe('applyDiscount', () => {
  it('applies a discount to a price', () => {
    const result = applyDiscount(100, 10);
    expect(result).toBe(90);
  });

  it('throws on a negative discount', () => {
    expect(() => applyDiscount(100, -5)).toThrow();
  });

  // No test for price === 0, daysUsed > totalDays, or totalDays === 0
});
