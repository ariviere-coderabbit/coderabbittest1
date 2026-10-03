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

  const currencies = new Set([...paid, ...refunded].map((c) => c.currency));
  if (currencies.size > 1) {
    throw new Error("Billing summary requires a single currency for paid and refunded cycles");
  }
  if (paid.some((c) => !Number.isFinite(c.billingPeriodDays) || c.billingPeriodDays <= 0)) {
    throw new Error("Paid billingPeriodDays must be finite and positive");
  }

  const totalRevenue = paid.reduce((sum, c) => sum + c.amount, 0);
  const refundedAmount = refunded.reduce((sum, c) => sum + c.amount, 0);
  const netRevenue = parseFloat((totalRevenue - refundedAmount).toFixed(2));

  const mrr = parseFloat(
    paid.reduce((sum, c) => sum + c.amount * 30 / c.billingPeriodDays, 0).toFixed(2)
  );

  const userCount = new Set(cycles.map((c) => c.userId)).size;
  const averageRevenuePerUser = parseFloat(
    (totalRevenue / userCount).toFixed(2)
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
    Object.create(null) as Record<string, BillingCycle[]>
  );
}

/** Exchange rate map from source currency to target currency. */
export type ExchangeRates = Record<string, number>;

/**
 * Normalize all BillingCycle amounts to a single target currency using the
 * provided exchange rates.
 *
 * @param cycles       - Array of billing cycles, possibly mixed currencies
 * @param targetCurrency - ISO 4217 code to convert amounts into (e.g. "USD")
 * @param rates        - Map of { "EUR": 1.08, "GBP": 1.27, ... } relative to targetCurrency
 * @returns New cycle objects with amount and currency rewritten; originals unchanged
 * @throws Error if a cycle's currency is missing from `rates` (and isn't already `targetCurrency`)
 */
export function normalizeCurrencies(
  cycles: BillingCycle[],
  targetCurrency: string,
  rates: ExchangeRates,
): BillingCycle[] {
  return cycles.map((cycle) => {
    if (cycle.currency === targetCurrency) {
      return cycle;
    }
    const rate = rates[cycle.currency];
    if (rate === undefined) {
      throw new Error(
        `No exchange rate provided for currency "${cycle.currency}" → "${targetCurrency}"`,
      );
    }
    return {
      ...cycle,
      amount: parseFloat((cycle.amount * rate).toFixed(2)),
      currency: targetCurrency,
    };
  });
}

export function detectAnomalies(
  cycles: BillingCycle[],
  thresholdMultiplier = 2.5
): BillingCycle[] {
  const paid = cycles.filter((c) => c.status === "paid");
  if (paid.length < 2) return [];

  const amounts = paid.map((c) => c.amount);
  const mean = amounts.reduce((a, b) => a + b, 0) / amounts.length;

  const variance =
    amounts.reduce((sum, a) => sum + Math.pow(a - mean, 2), 0) / amounts.length;
  const stddev = Math.sqrt(variance);

  return paid.filter((c) => Math.abs(c.amount - mean) > thresholdMultiplier * stddev);
}
