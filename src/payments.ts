export interface RefundRequest {
  totalPaid: number;
  daysUsed: number;
  totalDays: number;
}

export function calculateProRatedRefund(request: RefundRequest): number {
  const { totalPaid, daysUsed, totalDays } = request;

  if (
    !Number.isFinite(totalPaid) || !Number.isFinite(daysUsed) || !Number.isFinite(totalDays) ||
    totalPaid < 0 || totalDays <= 0 || daysUsed < 0 || daysUsed > totalDays
  ) {
    throw new Error(`Invalid refund request: totalPaid=${totalPaid}, daysUsed=${daysUsed}, totalDays=${totalDays}`);
  }

  const dailyRate = totalPaid / totalDays;
  const remainingDays = totalDays - daysUsed;
  const refund = dailyRate * remainingDays;

  return parseFloat(refund.toFixed(2));
}

export function applyDiscount(price: number, discountPercent: number): number {
  if (!Number.isFinite(discountPercent) || discountPercent < 0 || discountPercent > 100) {
    throw new Error(`Invalid discount percentage: ${discountPercent}`);
  }
  if (!Number.isFinite(price) || price < 0) {
    throw new Error(`Invalid price: ${price}`);
  }
  return parseFloat((price * (1 - discountPercent / 100)).toFixed(2));
}
