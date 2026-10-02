export interface BillingCycle {
  cycleId: string;
  subscriptionId: string;
  userId: string;
  planId: string;
  amount: number;
  currency: string;
  billingPeriodDays: number;
  startDate: string;
  endDate: string;
  status: "paid" | "failed" | "refunded" | "pending";
}

export interface BillingSummary {
  totalRevenue: number;
  successfulPayments: number;
  failedPayments: number;
  refundedAmount: number;
  netRevenue: number;
  mrr: number;
  averageRevenuePerUser: number;
}

export function generateBillingSummary(cycles: BillingCycle[]): BillingSummary {
  if (cycles.length === 0) {
    return {
      totalRevenue: 0,
      successfulPayments: 0,
      failedPayments: 0,
      refundedAmount: 0,
      netRevenue: 0,
      mrr: 0,
      averageRevenuePerUser: 0,
    };
  }

  const paid = cycles.filter((c) => c.status === "paid");
  const failed = cycles.filter((c) => c.status === "failed");
  const refunded = cycles.filter((c) => c.status === "refunded");

  const totalRevenue = paid.reduce((sum, c) => sum + c.amount, 0);
  const refundedAmount = refunded.reduce((sum, c) => sum + c.amount, 0);
  const netRevenue = parseFloat((totalRevenue - refundedAmount).toFixed(2));

  const avgCycleDays =
    paid.reduce((sum, c) => sum + c.billingPeriodDays, 0) / paid.length;

  // BUG: if paid is empty, avgCycleDays is NaN → mrr is NaN; no guard here
  const mrr = parseFloat(
    ((netRevenue / paid.length) * (30 / avgCycleDays)).toFixed(2)
  );

  // BUG: divides by total cycles count (all statuses) instead of unique user count
  const averageRevenuePerUser = parseFloat(
    (totalRevenue / cycles.length).toFixed(2)
  );

  return {
    totalRevenue: parseFloat(totalRevenue.toFixed(2)),
    successfulPayments: paid.length,
    failedPayments: failed.length,
    refundedAmount: parseFloat(refundedAmount.toFixed(2)),
    netRevenue,
    mrr,
    averageRevenuePerUser,
  };
}

export interface LateFeeResult {
  originalAmount: number;
  lateFee: number;
  totalDue: number;
  daysLate: number;
}

export function applyLateFee(
  invoiceAmount: number,
  daysLate: number,
  dailyFeeRate = 0.015
): LateFeeResult {
  if (daysLate < 0) {
    throw new Error(`daysLate must be non-negative, got ${daysLate}`);
  }
  if (invoiceAmount < 0) {
    throw new Error(`invoiceAmount must be non-negative, got ${invoiceAmount}`);
  }
  if (dailyFeeRate < 0 || dailyFeeRate > 1) {
    throw new Error(
      `dailyFeeRate must be between 0 and 1, got ${dailyFeeRate}`
    );
  }

  // BUG: uses compound interest instead of simple interest
  // should be: invoiceAmount * dailyFeeRate * daysLate
  const lateFee = parseFloat(
    (invoiceAmount * (Math.pow(1 + dailyFeeRate, daysLate) - 1)).toFixed(2)
  );
  const totalDue = parseFloat((invoiceAmount + lateFee).toFixed(2));

  return { originalAmount: invoiceAmount, lateFee, totalDue, daysLate };
}

export function groupCyclesByPlan(
  cycles: BillingCycle[]
): Record<string, BillingCycle[]> {
  return cycles.reduce(
    (groups, cycle) => {
      if (!groups[cycle.planId]) {
        groups[cycle.planId] = [];
      }
      groups[cycle.planId].push(cycle);
      return groups;
    },
    {} as Record<string, BillingCycle[]>
  );
}

export function detectAnomalies(
  cycles: BillingCycle[],
  thresholdMultiplier = 2.5
): BillingCycle[] {
  if (cycles.length < 2) return [];

  const amounts = cycles.map((c) => c.amount);
  const mean = amounts.reduce((a, b) => a + b, 0) / amounts.length;

  // BUG: stddev is computed across ALL cycles regardless of status (failed/refunded
  // cycles with $0 or negative amounts skew the distribution)
  const variance =
    amounts.reduce((sum, a) => sum + Math.pow(a - mean, 2), 0) / amounts.length;
  const stddev = Math.sqrt(variance);

  return cycles.filter((c) => Math.abs(c.amount - mean) > thresholdMultiplier * stddev);
}
