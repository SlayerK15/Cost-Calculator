"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import * as api from "@/lib/api";

export default function HomePage() {
  const [stats, setStats] = useState<{ total_deployments: number; total_configs: number } | null>(null);

  useEffect(() => {
    api.getAnalyticsSummary().then(setStats).catch(() => {});
  }, []);

  return (
    <div className="flex flex-col items-center">
      {/* Hero Section */}
      <section className="relative w-full pt-20 pb-16 text-center overflow-hidden">
        {/* Animated gradient background */}
        <div className="absolute inset-0 -z-10">
          <div className="absolute inset-0 bg-gradient-to-br from-brand-900/30 via-gray-950 to-blue-900/20" />
          <div className="absolute top-0 left-1/4 w-96 h-96 bg-brand-600/10 rounded-full blur-3xl animate-pulse" />
          <div className="absolute bottom-0 right-1/4 w-80 h-80 bg-blue-600/10 rounded-full blur-3xl animate-pulse [animation-delay:1s]" />
        </div>

        <h1 className="text-5xl md:text-6xl font-bold leading-tight max-w-4xl mx-auto">
          The <span className="text-brand-400">Complete Platform</span> for
          <br />LLM Cloud Deployment
        </h1>
        <p className="mt-6 max-w-2xl mx-auto text-lg text-gray-400">
          Calculate costs, build custom models, and deploy to any cloud.
          From free cost estimation to fully managed enterprise infrastructure.
        </p>

        {/* Platform stats */}
        {stats && (
          <div className="mt-8 flex justify-center gap-8">
            <div className="text-center">
              <div className="text-2xl font-bold text-white">{stats.total_configs || 0}+</div>
              <div className="text-xs text-gray-500 uppercase tracking-wider">Models Configured</div>
            </div>
            <div className="w-px h-10 bg-gray-800" />
            <div className="text-center">
              <div className="text-2xl font-bold text-white">{stats.total_deployments || 0}+</div>
              <div className="text-xs text-gray-500 uppercase tracking-wider">Deployments</div>
            </div>
            <div className="w-px h-10 bg-gray-800" />
            <div className="text-center">
              <div className="text-2xl font-bold text-white">3</div>
              <div className="text-xs text-gray-500 uppercase tracking-wider">Cloud Providers</div>
            </div>
          </div>
        )}

        <div className="mt-10 flex flex-wrap justify-center gap-4">
          <Link href="/estimate" className="btn-primary text-lg px-8 py-3">
            Calculate Costs Free
          </Link>
          <Link href="/pricing" className="btn-secondary text-lg px-8 py-3">
            View Plans
          </Link>
        </div>
      </section>

      {/* Workflow Pipeline */}
      <section className="w-full max-w-5xl py-16">
        <h2 className="text-2xl font-bold text-center mb-2">How It Works</h2>
        <p className="text-center text-gray-400 text-sm mb-10">
          Four steps from estimation to production
        </p>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[
            { step: "1", title: "Calculate", desc: "Estimate VRAM, GPU, and monthly costs across AWS, GCP, Azure", color: "text-green-400" },
            { step: "2", title: "Build", desc: "Compose models with LoRA adapters, merges, and quantization", color: "text-blue-400" },
            { step: "3", title: "Deploy", desc: "Download IaC configs or let us manage the infrastructure", color: "text-purple-400" },
            { step: "4", title: "Monitor", desc: "Track requests, latency, costs, and auto-scaling in real time", color: "text-yellow-400" },
          ].map((item) => (
            <div key={item.step} className="card text-center relative">
              <div className={`text-3xl font-bold mb-3 ${item.color}`}>{item.step}</div>
              <h3 className="font-semibold text-white mb-1">{item.title}</h3>
              <p className="text-sm text-gray-400">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Feature grid */}
      <section className="w-full max-w-5xl py-12">
        <h2 className="text-2xl font-bold text-center mb-8">Platform Features</h2>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <FeatureCard
            title="Cost Estimation"
            description="Calculate VRAM, GPU requirements, and monthly costs across AWS, GCP, and Azure with detailed breakdowns."
            tier="free"
          />
          <FeatureCard
            title="Multi-Cloud Compare"
            description="Compare pricing across all three major cloud providers side-by-side to find the best value."
            tier="free"
          />
          <FeatureCard
            title="API Provider Comparison"
            description="Compare self-hosting costs vs API providers like OpenAI, Anthropic, and Google."
            tier="free"
          />
          <FeatureCard
            title="No-Code Model Builder"
            description="Compose models with LoRA adapters, model merges (SLERP, TIES, DARE), and quantization — no code required."
            tier="pro"
          />
          <FeatureCard
            title="Visual Pipeline Builder"
            description="Drag-and-drop pipeline canvas to visually configure your model composition workflow."
            tier="pro"
          />
          <FeatureCard
            title="Model Playground"
            description="Test your model configs with simulated inference before deploying to production."
            tier="pro"
          />
          <FeatureCard
            title="Self-Deploy Wizard"
            description="Generate Dockerfiles, K8s manifests, Terraform configs, and CI/CD pipelines for any cloud."
            tier="pro"
          />
          <FeatureCard
            title="Managed Deployment"
            description="We provision and manage the infrastructure — GPUs, auto-scaling, health monitoring, all handled."
            tier="enterprise"
          />
          <FeatureCard
            title="Cost Alerts & Budgets"
            description="Set monthly budgets, threshold alerts, and track real-time spend across all deployments."
            tier="enterprise"
          />
        </div>
      </section>

      {/* Comparison Table */}
      <section className="w-full max-w-4xl py-16">
        <h2 className="text-2xl font-bold text-center mb-8">Self-Host vs API vs Our Platform</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-left text-gray-500">
                <th className="py-3 px-4">Feature</th>
                <th className="py-3 px-4 text-center">API Providers</th>
                <th className="py-3 px-4 text-center">Self-Hosted (DIY)</th>
                <th className="py-3 px-4 text-center text-brand-400">LLM Cloud Platform</th>
              </tr>
            </thead>
            <tbody className="text-gray-300">
              {[
                ["Cost Transparency", "Limited", "Full control", "Full + estimation tools"],
                ["Setup Time", "Minutes", "Days-weeks", "Minutes-hours"],
                ["Custom Models", "No", "Yes", "Yes + visual builder"],
                ["Data Privacy", "Shared infra", "Full control", "Full control"],
                ["Scaling", "Automatic", "Manual setup", "Auto-scaling included"],
                ["Cost at Scale", "$$$$", "$$", "$$ (optimized)"],
                ["Monitoring", "Basic", "Build your own", "Built-in dashboard"],
                ["Infrastructure Mgmt", "None needed", "All on you", "Optional managed"],
              ].map(([feature, apiCol, selfCol, ourCol]) => (
                <tr key={feature} className="border-b border-gray-800/50">
                  <td className="py-3 px-4 text-gray-400">{feature}</td>
                  <td className="py-3 px-4 text-center">{apiCol}</td>
                  <td className="py-3 px-4 text-center">{selfCol}</td>
                  <td className="py-3 px-4 text-center font-medium text-white">{ourCol}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Supported models */}
      <section className="w-full max-w-4xl py-12">
        <h2 className="text-2xl font-bold text-center">Supported Models</h2>
        <p className="mt-2 text-sm text-gray-500 text-center">
          Estimate costs for any of these models or enter custom parameters
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          {[
            "LLaMA 3.1", "Mistral", "Mixtral", "Gemma 2",
            "Qwen 2", "Phi-3", "DeepSeek", "Custom Parameters",
          ].map((m) => (
            <span
              key={m}
              className="rounded-full border border-gray-700 bg-gray-800 px-4 py-1.5 text-sm text-gray-300"
            >
              {m}
            </span>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="w-full max-w-2xl py-16">
        <div className="card text-center">
          <h2 className="text-2xl font-bold text-white">Ready to get started?</h2>
          <p className="mt-2 text-gray-400">
            Start with our free cost calculator, then scale to managed deployment when ready.
          </p>
          <div className="mt-6 flex justify-center gap-4">
            <Link href="/estimate" className="btn-primary px-6 py-2.5">
              Free Calculator
            </Link>
            <Link href="/pricing" className="btn-secondary px-6 py-2.5">
              View Plans
            </Link>
            <Link href="/auth" className="px-6 py-2.5 text-sm text-gray-400 hover:text-white border border-gray-700 hover:border-gray-600 rounded-lg transition">
              Sign Up
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

function FeatureCard({
  title,
  description,
  tier,
}: {
  title: string;
  description: string;
  tier: "free" | "pro" | "enterprise";
}) {
  const tierConfig = {
    free: { label: "Free", classes: "bg-green-900/40 border-green-800 text-green-400" },
    pro: { label: "Pro", classes: "bg-blue-900/40 border-blue-800 text-blue-400" },
    enterprise: { label: "Enterprise", classes: "bg-purple-900/40 border-purple-800 text-purple-400" },
  };
  const t = tierConfig[tier];

  return (
    <div className="card text-left">
      <div className="flex items-center gap-2">
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${t.classes}`}>
          {t.label}
        </span>
      </div>
      <p className="mt-2 text-sm text-gray-400">{description}</p>
    </div>
  );
}
