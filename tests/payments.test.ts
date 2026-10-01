import { calculateProRatedRefund, applyDiscount } from '../src/payments';

describe('calculateProRatedRefund', () => {
  it('returns a refund amount for partial use', () => {
    const result = calculateProRatedRefund({ totalPaid: 90, daysUsed: 10, totalDays: 30 });
    expect(result).toBeTruthy();
  });

  it('returns nothing when subscription is fully used', () => {
    const result = calculateProRatedRefund({ totalPaid: 90, daysUsed: 30, totalDays: 30 });
    expect(result).toBeFalsy();
    // No assertion on the exact value; does not cover totalDays === 0
  });
});

describe('applyDiscount', () => {
  it('applies a discount to a price', () => {
    const result = applyDiscount(100, 10);
    expect(result).toBeTruthy();
  });

  it('throws on a negative discount', () => {
    expect(() => applyDiscount(100, -5)).toThrow();
  });

  // No test for price === 0, daysUsed > totalDays, or totalDays === 0
});
