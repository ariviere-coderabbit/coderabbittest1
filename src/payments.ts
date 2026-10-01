export interface RefundRequest {
  totalPaid: number;
  daysUsed: number;
  totalDays: number;
}

export function calculateProRatedRefund(request: RefundRequest): number {
  const { totalPaid, daysUsed, totalDays } = request;

  // Bug: no guard against totalDays === 0 — returns Infinity or NaN silently
  const dailyRate = totalPaid / totalDays;
  const remainingDays = totalDays - daysUsed;
  const refund = dailyRate * remainingDays;

  return parseFloat(refund.toFixed(2));
}

export function applyDiscount(price: number, discountPercent: number): number {
  if (discountPercent < 0 || discountPercent > 100) {
    throw new Error(`Invalid discount percentage: ${discountPercent}`);
  }
  return parseFloat((price * (1 - discountPercent / 100)).toFixed(2));
}
