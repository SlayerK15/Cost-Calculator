"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import * as api from "@/lib/api";

const TIERS = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    tierKey: "free",
    description: "Perfect for evaluating LLM deployment costs",
    features: [
      "LLM Cost Calculator",
      "Multi-cloud comparison (AWS, GCP, Azure)",
      "API provider comparison",
      "Popular model library",
      "VRAM & GPU recommendations",
    ],
    cta: "Get Started",
    ctaAction: "estimate",
    highlighted: false,
  },
  {
    name: "Pro",
    price: "$49",
    period: "/month",
    tierKey: "pro",
    description: "Build and deploy custom LLM configurations",
    features: [
      "Everything in Free",
      "No-code Model Builder",
      "LoRA adapter support",
      "Model merging (SLERP, TIES, DARE)",
      "Quantization (GPTQ, AWQ, BNB)",
      "Self-deploy wizard & IaC generation",
      "Model Playground",
      "Version history & config management",
    ],
    cta: "Upgrade to Pro",
    ctaAction: "pro",
    highlighted: true,
  },
  {
    name: "Enterprise",
    price: "$199",
    period: "/month",
    tierKey: "enterprise",
    description: "Fully managed cloud deployment & monitoring",
    features: [
      "Everything in Pro",
      "Managed cloud deployment",
      "Cloud credential management",
      "One-click provisioning",
      "Auto-scaling",
      "Monitoring dashboard",
      "Cost alerts & budgets",
      "Priority support",
    ],
    cta: "Upgrade to Enterprise",
    ctaAction: "enterprise",
    highlighted: false,
  },
];

export default function PricingPage() {
  const router = useRouter();
  const [upgrading, setUpgrading] = useState("");
  const [currentTier, setCurrentTier] = useState<string | null>(null);

  useEffect(() => {
    if (api.isAuthenticated()) {
      api.getSubscriptionStatus().then((s) => setCurrentTier(s.tier)).catch(() => {});
    }
  }, []);

  async function handleUpgrade(tier: string) {
    if (tier === "estimate") {
      router.push("/estimate");
      return;
    }
    if (!api.isAuthenticated()) {
      router.push("/auth");
      return;
    }
    setUpgrading(tier);
    try {
      // Try Stripe checkout first
      const checkout = await api.createCheckoutSession(tier);
      window.location.href = checkout.checkout_url;
      return;
    } catch {
      // Stripe not configured — fall back to dev mode direct upgrade
      try {
        await api.upgradeSubscription(tier);
        router.push(tier === "pro" ? "/builder" : "/dashboard");
      } catch (err: any) {
        alert(err.message);
      }
    }
    setUpgrading("");
  }

  async function handleManageBilling() {
    try {
      const portal = await api.createPortalSession();
      window.location.href = portal.portal_url;
    } catch (err: any) {
      alert(err.message);
    }
  }

  function getCtaLabel(tier: typeof TIERS[number]) {
    if (!currentTier) return tier.cta;
    if (tier.tierKey === currentTier) return "Current Plan";
    if (tier.tierKey === "free" && currentTier !== "free") return "Included";
    return tier.cta;
  }

  function isDisabled(tierKey: string) {
    if (!currentTier) return false;
    const order: Record<string, number> = { free: 0, pro: 1, enterprise: 2 };
    return order[tierKey] <= order[currentTier];
  }

  return (
    <div className="py-8">
      <div className="text-center mb-12">
        <h1 className="text-3xl font-bold text-white mb-3">
          Choose Your Plan
        </h1>
        <p className="text-gray-400 max-w-xl mx-auto">
          Start free with our cost calculator. Upgrade to build custom models
          and deploy them to the cloud.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3 max-w-5xl mx-auto">
        {TIERS.map((tier) => {
          const isCurrent = tier.tierKey === currentTier;

          return (
            <div
              key={tier.name}
              className={`rounded-xl border p-6 flex flex-col ${
                isCurrent
                  ? "border-green-500 bg-green-600/5 ring-1 ring-green-500/20"
                  : tier.highlighted
                  ? "border-brand-500 bg-brand-600/5 ring-1 ring-brand-500/20"
                  : "border-gray-700 bg-gray-800/50"
              }`}
            >
              {isCurrent && (
                <div className="text-xs font-semibold text-green-400 uppercase tracking-wider mb-2">
                  Your Current Plan
                </div>
              )}
              {!isCurrent && tier.highlighted && (
                <div className="text-xs font-semibold text-brand-400 uppercase tracking-wider mb-2">
                  Most Popular
                </div>
              )}
              <h2 className="text-xl font-bold text-white">{tier.name}</h2>
              <div className="mt-2 flex items-baseline gap-1">
                <span className="text-3xl font-bold text-white">
                  {tier.price}
                </span>
                <span className="text-gray-400 text-sm">{tier.period}</span>
              </div>
              <p className="text-sm text-gray-400 mt-2">{tier.description}</p>

              <ul className="mt-6 space-y-2 flex-1">
                {tier.features.map((feature) => (
                  <li
                    key={feature}
                    className="flex items-start gap-2 text-sm text-gray-300"
                  >
                    <span className="text-brand-400 mt-0.5 shrink-0">
                      &#10003;
                    </span>
                    {feature}
                  </li>
                ))}
              </ul>

              <button
                onClick={() => handleUpgrade(tier.ctaAction)}
                disabled={upgrading === tier.ctaAction || (isDisabled(tier.tierKey) && tier.tierKey !== "free")}
                className={`mt-6 w-full rounded-lg py-2.5 text-sm font-medium transition ${
                  isCurrent
                    ? "bg-green-900/30 text-green-400 border border-green-800 cursor-default"
                    : tier.highlighted
                    ? "bg-brand-600 text-white hover:bg-brand-500"
                    : "bg-gray-700 text-white hover:bg-gray-600"
                } disabled:opacity-50`}
              >
                {upgrading === tier.ctaAction ? "Redirecting..." : getCtaLabel(tier)}
              </button>
            </div>
          );
        })}
      </div>

      {/* Manage billing for subscribers with Stripe */}
      {currentTier && currentTier !== "free" && (
        <div className="text-center mt-8">
          <button
            onClick={handleManageBilling}
            className="text-sm text-gray-400 hover:text-white underline underline-offset-4 transition"
          >
            Manage Billing & Subscription
          </button>
        </div>
      )}

      <div className="text-center mt-12 text-sm text-gray-500">
        All plans include access to our free LLM Cost Calculator.
        <br />
        Secure payments powered by Stripe. Upgrade or downgrade anytime.
      </div>
    </div>
  );
}
