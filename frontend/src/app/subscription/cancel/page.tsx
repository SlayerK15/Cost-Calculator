"use client";

import Link from "next/link";

export default function SubscriptionCancelPage() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 bg-gray-800 rounded-full flex items-center justify-center mb-6">
        <span className="text-3xl text-gray-400">&#10005;</span>
      </div>

      <h1 className="text-3xl font-bold text-white mb-3">
        Checkout Canceled
      </h1>

      <p className="text-gray-400 max-w-md mb-8">
        No worries — you weren&apos;t charged. You can upgrade anytime when
        you&apos;re ready.
      </p>

      <div className="flex gap-4">
        <Link href="/pricing" className="btn-primary px-6 py-2.5">
          Back to Pricing
        </Link>
        <Link href="/estimate" className="btn-secondary px-6 py-2.5">
          Free Calculator
        </Link>
      </div>
    </div>
  );
}
