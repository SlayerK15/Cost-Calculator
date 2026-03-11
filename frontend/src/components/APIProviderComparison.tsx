"use client";

import type { APIProviderComparison } from "@/types";

const PROVIDER_COLORS: Record<string, string> = {
  OpenAI: "bg-green-500",
  Anthropic: "bg-orange-500",
  Google: "bg-blue-500",
  Mistral: "bg-purple-500",
  DeepSeek: "bg-gray-400",
  "Self-Hosted": "bg-brand-500",
};

// Chat subscriptions for context — these are flat-rate, rate-limited plans
const CHAT_SUBSCRIPTIONS = [
  { provider: "OpenAI", plan: "ChatGPT Plus", price: 20, limit: "Rate-limited (~80 msgs/3hrs on GPT-4o)" },
  { provider: "OpenAI", plan: "ChatGPT Pro", price: 200, limit: "Higher limits, o1-pro access" },
  { provider: "Anthropic", plan: "Claude Pro", price: 20, limit: "5x more usage than free tier" },
  { provider: "Anthropic", plan: "Claude Max", price: 100, limit: "20x more usage than free tier" },
  { provider: "Google", plan: "Gemini Advanced", price: 20, limit: "Rate-limited, 1M token context" },
  { provider: "DeepSeek", plan: "DeepSeek Chat", price: 0, limit: "Free chat with rate limits" },
];

function formatCostPerReq(cost: number): string {
  if (cost < 0.0001) return `$${cost.toFixed(6)}`;
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(3)}`;
}

export function APIProviderComparisonCard({
  data,
}: {
  data: APIProviderComparison;
}) {
  // Self-hosted cost per request
  const selfHostedCostPerReq =
    data.monthly_requests > 0
      ? data.self_hosted_monthly / data.monthly_requests
      : 0;

  // For bar chart: use cost per request as the normalizing unit
  const maxCostPerReq = Math.max(
    ...data.api_providers.map((p) => p.cost_per_request),
    selfHostedCostPerReq
  );

  // Count cheaper/more expensive by cost per request
  const cheaperByReq = data.api_providers.filter(
    (p) => p.cost_per_request < selfHostedCostPerReq
  ).length;
  const moreExpensiveByReq = data.api_providers.length - cheaperByReq;

  // Breakeven: for each API provider, at what monthly request count does self-hosted become cheaper?
  // Self-hosted = fixed $X/mo, API = cost_per_request * N
  // Breakeven N = self_hosted_monthly / cost_per_request
  const breakevenData = data.api_providers.map((p) => ({
    provider: p.provider,
    model: p.model,
    costPerReq: p.cost_per_request,
    breakeven: p.cost_per_request > 0 ? Math.ceil(data.self_hosted_monthly / p.cost_per_request) : Infinity,
  }));

  // Median breakeven across all providers
  const sortedBreakevens = breakevenData
    .filter((b) => b.breakeven < Infinity)
    .sort((a, b) => a.breakeven - b.breakeven);
  const medianBreakeven = sortedBreakevens.length > 0
    ? sortedBreakevens[Math.floor(sortedBreakevens.length / 2)].breakeven
    : 0;

  const totalInputTokens = (data.monthly_input_tokens / 1_000_000).toFixed(1);
  const totalOutputTokens = (data.monthly_output_tokens / 1_000_000).toFixed(1);

  return (
    <div className="card">
      <h3 className="text-lg font-bold text-white">
        Self-Hosted vs API Providers
      </h3>
      <p className="mt-1 text-sm text-gray-400">
        Based on{" "}
        <span className="text-white font-medium">
          {data.monthly_requests.toLocaleString()}
        </span>{" "}
        requests/month ({data.avg_input_tokens_per_request} input +{" "}
        {data.avg_output_tokens_per_request} output tokens per request)
      </p>

      {/* Breakeven insight */}
      <div className="mt-3 rounded-lg border border-brand-700 bg-brand-900/20 p-3">
        <p className="text-sm text-brand-300">
          <span className="font-bold">Breakeven point:</span>{" "}
          Self-hosting becomes cheaper than most API providers at{" "}
          <span className="font-bold text-white">
            {medianBreakeven.toLocaleString()}
          </span>{" "}
          requests/month. You're at{" "}
          <span className="font-bold text-white">
            {data.monthly_requests.toLocaleString()}
          </span>
          {data.monthly_requests >= medianBreakeven ? (
            <span className="text-green-400 font-bold">
              {" "}— self-hosting is the better deal.
            </span>
          ) : (
            <span className="text-yellow-400 font-bold">
              {" "}— increase volume to break even.
            </span>
          )}
        </p>
      </div>

      <div className="mt-2 rounded-md border border-blue-800/50 bg-blue-900/20 px-3 py-2 text-xs text-blue-300">
        <p className="font-medium">How costs are compared</p>
        <p className="mt-0.5 text-blue-400">
          All costs normalized to <span className="text-white font-medium">$/request</span>.
          Self-hosted is a fixed cost ({`$${data.self_hosted_monthly.toLocaleString()}/mo`}) divided by your
          request volume — the more you use it, the cheaper each request gets.
          API providers charge per token and the cost per request stays constant regardless of volume.
          Your usage: {totalInputTokens}M input + {totalOutputTokens}M output tokens/month.
        </p>
      </div>

      {/* Summary banner */}
      {moreExpensiveByReq > 0 && (
        <div className="mt-4 rounded-lg border border-green-800 bg-green-900/20 p-3">
          <p className="text-sm text-green-300">
            At your volume, self-hosting at{" "}
            <span className="font-bold text-white">
              {formatCostPerReq(selfHostedCostPerReq)}/req
            </span>
            {" "}is cheaper than{" "}
            <span className="font-bold">{moreExpensiveByReq}</span> of{" "}
            {data.api_providers.length} API providers.
            {" "}Double your traffic and it drops to{" "}
            <span className="font-bold text-green-200">
              {formatCostPerReq(selfHostedCostPerReq / 2)}/req
            </span>
            {" "}while API costs stay the same.
          </p>
        </div>
      )}

      {/* Bar chart comparison — cost per request */}
      <div className="mt-6 space-y-3">
        <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">Cost per request</p>
        {/* Self-hosted bar (always first) */}
        <ComparisonBar
          label={`Self-Hosted (${data.self_hosted_provider.toUpperCase()})`}
          value={selfHostedCostPerReq}
          displayValue={`${formatCostPerReq(selfHostedCostPerReq)}/req`}
          maxValue={maxCostPerReq}
          color="bg-brand-500"
          highlight
          subtitle={`$${data.self_hosted_monthly.toLocaleString()}/mo fixed — no rate limits`}
        />

        {/* Divider */}
        <div className="border-t border-gray-700 my-2" />

        {/* API provider bars */}
        {data.api_providers.map((p) => (
          <ComparisonBar
            key={`${p.provider}-${p.model}`}
            label={`${p.provider} — ${p.model}`}
            value={p.cost_per_request}
            displayValue={`${formatCostPerReq(p.cost_per_request)}/req`}
            maxValue={maxCostPerReq}
            color={PROVIDER_COLORS[p.provider] || "bg-gray-500"}
            cheaper={p.cost_per_request < selfHostedCostPerReq}
            moreExpensive={p.cost_per_request > selfHostedCostPerReq}
            subtitle={`$${p.monthly_cost.toLocaleString()}/mo at your volume — rate-limited`}
          />
        ))}
      </div>

      {/* Detailed table */}
      <div className="mt-6 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-gray-700 text-gray-500">
            <tr>
              <th className="pb-2 pr-4">Provider</th>
              <th className="pb-2 pr-4">Type</th>
              <th className="pb-2 pr-4 text-right">$/Request</th>
              <th className="pb-2 pr-4 text-right">Monthly</th>
              <th className="pb-2 pr-4 text-right">Breakeven</th>
              <th className="pb-2 text-right">vs Self-Hosted</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            <tr className="bg-brand-900/10">
              <td className="py-2.5 pr-4 font-medium text-brand-400">
                Self-Hosted ({data.self_hosted_provider.toUpperCase()})
              </td>
              <td className="py-2.5 pr-4">
                <span className="inline-flex items-center rounded-full bg-brand-900/40 px-2 py-0.5 text-[10px] font-medium text-brand-300">
                  Dedicated GPU
                </span>
              </td>
              <td className="py-2.5 pr-4 text-right font-bold text-white">
                {formatCostPerReq(selfHostedCostPerReq)}
              </td>
              <td className="py-2.5 pr-4 text-right font-bold text-white">
                ${data.self_hosted_monthly.toLocaleString()}
              </td>
              <td className="py-2.5 pr-4 text-right text-gray-500">—</td>
              <td className="py-2.5 text-right text-gray-500">baseline</td>
            </tr>
            {data.api_providers.map((p) => {
              const diffPerReq = p.cost_per_request - selfHostedCostPerReq;
              const pctPerReq =
                selfHostedCostPerReq > 0
                  ? ((diffPerReq / selfHostedCostPerReq) * 100).toFixed(0)
                  : "—";
              const breakeven = p.cost_per_request > 0
                ? Math.ceil(data.self_hosted_monthly / p.cost_per_request)
                : Infinity;
              const userAboveBreakeven = data.monthly_requests >= breakeven;
              return (
                <tr key={`${p.provider}-${p.model}`}>
                  <td className="py-2.5 pr-4 font-medium text-gray-300">
                    {p.provider}{" "}
                    <span className="text-gray-500">{p.model}</span>
                  </td>
                  <td className="py-2.5 pr-4">
                    <span className="inline-flex items-center rounded-full bg-blue-900/30 px-2 py-0.5 text-[10px] font-medium text-blue-400">
                      Pay-per-token
                    </span>
                  </td>
                  <td className="py-2.5 pr-4 text-right text-gray-400">
                    {formatCostPerReq(p.cost_per_request)}
                  </td>
                  <td className="py-2.5 pr-4 text-right font-medium text-white">
                    ${p.monthly_cost.toLocaleString()}
                  </td>
                  <td className={`py-2.5 pr-4 text-right text-xs ${userAboveBreakeven ? "text-green-400" : "text-gray-500"}`}>
                    {breakeven < Infinity ? (
                      <>
                        {breakeven.toLocaleString()} req/mo
                        {userAboveBreakeven && <span className="ml-1">&#10003;</span>}
                      </>
                    ) : "—"}
                  </td>
                  <td
                    className={`py-2.5 text-right font-medium ${
                      diffPerReq > 0 ? "text-red-400" : "text-green-400"
                    }`}
                  >
                    {diffPerReq > 0 ? "+" : ""}
                    {pctPerReq}%
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Why self-host callout */}
      <div className="mt-6 rounded-lg border border-gray-700 bg-gray-800/40 p-4">
        <h4 className="text-sm font-bold text-gray-200">
          Why self-host even when APIs look cheaper?
        </h4>
        <div className="mt-2 grid grid-cols-1 gap-1.5 sm:grid-cols-2 text-xs text-gray-400">
          <div><span className="text-brand-400 font-medium">No rate limits</span> — full control over throughput, no RPM/TPM caps</div>
          <div><span className="text-brand-400 font-medium">Data privacy</span> — data never leaves your infrastructure (HIPAA, GDPR)</div>
          <div><span className="text-brand-400 font-medium">Predictable cost</span> — fixed monthly, no surprise bills from traffic spikes</div>
          <div><span className="text-brand-400 font-medium">Customization</span> — fine-tuning, LoRA, custom inference pipelines</div>
          <div><span className="text-brand-400 font-medium">No vendor lock-in</span> — not dependent on provider uptime or pricing changes</div>
          <div><span className="text-brand-400 font-medium">Low latency</span> — deploy in your own VPC/region for minimal latency</div>
        </div>
      </div>

      {/* Chat subscription reference */}
      <div className="mt-6 rounded-lg border border-yellow-800/40 bg-yellow-900/10 p-4">
        <h4 className="text-sm font-bold text-yellow-300">
          Chat Subscriptions (not comparable)
        </h4>
        <p className="mt-1 text-xs text-yellow-400/80">
          These are consumer chat plans with rate limits — not the same as API
          access. They cannot handle{" "}
          {data.monthly_requests.toLocaleString()} requests/month programmatically.
        </p>
        <div className="mt-3 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
          {CHAT_SUBSCRIPTIONS.map((s) => (
            <div
              key={`${s.provider}-${s.plan}`}
              className="flex items-baseline gap-2 text-xs"
            >
              <span className="font-medium text-gray-300">{s.plan}</span>
              <span className="text-yellow-400 font-bold">
                {s.price === 0 ? "Free" : `$${s.price}/mo`}
              </span>
              <span className="text-gray-500 truncate">{s.limit}</span>
            </div>
          ))}
        </div>
      </div>

      <p className="mt-4 text-xs text-gray-600">
        API pricing based on published rates. Self-hosted cost includes compute,
        storage, bandwidth, and KV cache overhead. Actual costs may vary.
      </p>
    </div>
  );
}

function ComparisonBar({
  label,
  value,
  displayValue,
  maxValue,
  color,
  highlight = false,
  cheaper = false,
  moreExpensive = false,
  subtitle,
}: {
  label: string;
  value: number;
  displayValue: string;
  maxValue: number;
  color: string;
  highlight?: boolean;
  cheaper?: boolean;
  moreExpensive?: boolean;
  subtitle?: string;
}) {
  const width = maxValue > 0 ? Math.max((value / maxValue) * 100, 2) : 2;

  return (
    <div>
      <div className="flex items-center justify-between text-sm mb-1">
        <div>
          <span
            className={
              highlight
                ? "font-bold text-brand-400"
                : cheaper
                ? "text-green-400"
                : "text-gray-300"
            }
          >
            {label}
          </span>
          {subtitle && (
            <span className="ml-2 text-[10px] text-gray-600">{subtitle}</span>
          )}
        </div>
        <span
          className={
            highlight
              ? "font-bold text-white"
              : moreExpensive
              ? "text-red-400"
              : cheaper
              ? "text-green-400"
              : "text-gray-300"
          }
        >
          {displayValue}
        </span>
      </div>
      <div className="h-2.5 w-full rounded-full bg-gray-800">
        <div
          className={`h-2.5 rounded-full ${color} ${
            highlight ? "ring-1 ring-brand-400/50" : ""
          }`}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}
