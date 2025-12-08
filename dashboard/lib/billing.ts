export type BillingPlanId = 'free' | 'pro' | 'enterprise';

export interface BillingPlan {
  id: BillingPlanId;
  name: string;
  priceUsdPerMonth: number;
  description: string;
}

export interface CheckoutSession {
  sessionId: string;
  url: string;
  mode: 'dummy';
  planId: BillingPlanId;
}

export const BILLING_PLANS: BillingPlan[] = [
  {
    id: 'free',
    name: 'Free',
    priceUsdPerMonth: 0,
    description: 'Perfect for trying out Soulcaster with basic limits.',
  },
  {
    id: 'pro',
    name: 'Pro',
    priceUsdPerMonth: 29,
    description: 'For growing teams that want automated clustering and agent runs.',
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    priceUsdPerMonth: 99,
    description: 'Custom limits and priority support for serious production workloads.',
  },
];

export function getBillingPlan(planId: BillingPlanId): BillingPlan | undefined {
  return BILLING_PLANS.find((plan) => plan.id === planId);
}

/**
 * Create a dummy checkout session.
 *
 * This does not talk to Stripe yet. It just returns
 * a fake URL that the dashboard can redirect to, so
 * we can wire the UX and later swap the implementation
 * for a real Stripe integration.
 */
export async function createDummyCheckoutSession(planId: BillingPlanId): Promise<CheckoutSession> {
  const plan = getBillingPlan(planId);
  if (!plan) {
    throw new Error(`Unknown billing plan: ${planId}`);
  }

  const sessionId = `dummy_${planId}_${Date.now()}`;

  return {
    sessionId,
    planId,
    mode: 'dummy',
    url: `/billing/success?session_id=${encodeURIComponent(sessionId)}&plan=${encodeURIComponent(planId)}`,
  };
}

