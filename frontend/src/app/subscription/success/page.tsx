"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import * as api from "@/lib/api";

export default function SubscriptionSuccessPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const [tier, setTier] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Poll for tier update (webhook may take a moment)
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      try {
        const status = await api.getSubscriptionStatus();
        if (status.tier !== "free" || attempts > 10) {
          setTier(status.tier);
          setLoading(false);
          clearInterval(interval);
        }
      } catch {
        if (attempts > 10) {
          setLoading(false);
          clearInterval(interval);
        }
      }
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  const tierDisplay = tier?.toUpperCase() || "PRO";

  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 bg-green-600/20 rounded-full flex items-center justify-center mb-6">
        <span className="text-3xl text-green-400">&#10003;</span>
      </div>

      <h1 className="text-3xl font-bold text-white mb-3">
        Welcome to {tierDisplay}!
      </h1>

      {loading ? (
        <div className="flex items-center gap-2 text-gray-400 mb-6">
          <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-blue-500" />
          Activating your subscription...
        </div>
      ) : (
        <p className="text-gray-400 max-w-md mb-8">
          Your subscription is now active. You have full access to all{" "}
          <span className="text-white font-medium">{tierDisplay}</span> features.
        </p>
      )}

      <div className="flex gap-4">
        {tier === "enterprise" ? (
          <>
            <Link href="/managed" className="btn-primary px-6 py-2.5">
              Managed Deployments
            </Link>
            <Link href="/dashboard" className="btn-secondary px-6 py-2.5">
              Dashboard
            </Link>
          </>
        ) : (
          <>
            <Link href="/builder" className="btn-primary px-6 py-2.5">
              Open Model Builder
            </Link>
            <Link href="/playground" className="btn-secondary px-6 py-2.5">
              Try Playground
            </Link>
          </>
        )}
      </div>

      <Link
        href="/pricing"
        className="mt-8 text-sm text-gray-500 hover:text-gray-300 transition"
      >
        View all plan details
      </Link>
    </div>
  );
}
