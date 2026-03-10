"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  isAuthenticated,
  listCredentials,
  createCredential,
  validateCredential,
  deleteCredential,
  getSubscriptionStatus,
} from "@/lib/api";
import type { CloudCredential } from "@/types";

const PROVIDERS = [
  {
    id: "aws",
    name: "Amazon Web Services",
    icon: "☁️",
    fields: [
      { key: "aws_access_key_id", label: "Access Key ID", placeholder: "AKIA..." },
      { key: "aws_secret_access_key", label: "Secret Access Key", placeholder: "wJal...", secret: true },
    ],
  },
  {
    id: "gcp",
    name: "Google Cloud Platform",
    icon: "🌐",
    fields: [
      { key: "service_account_json", label: "Service Account JSON", placeholder: '{"type":"service_account",...}', multiline: true },
    ],
  },
  {
    id: "azure",
    name: "Microsoft Azure",
    icon: "🔷",
    fields: [
      { key: "tenant_id", label: "Tenant ID", placeholder: "xxxxxxxx-xxxx-..." },
      { key: "client_id", label: "Client ID", placeholder: "xxxxxxxx-xxxx-..." },
      { key: "client_secret", label: "Client Secret", placeholder: "secret...", secret: true },
      { key: "subscription_id", label: "Subscription ID", placeholder: "xxxxxxxx-xxxx-..." },
    ],
  },
];

export default function CredentialsPage() {
  const router = useRouter();
  const [credentials, setCredentials] = useState<CloudCredential[]>([]);
  const [loading, setLoading] = useState(true);
  const [tier, setTier] = useState<string>("free");

  // Add form state
  const [showForm, setShowForm] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string>("");
  const [label, setLabel] = useState("");
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [validating, setValidating] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/auth/login");
      return;
    }
    loadData();
  }, []);

  async function loadData() {
    try {
      const sub = await getSubscriptionStatus();
      setTier(sub.tier);
      if (sub.tier === "enterprise") {
        const creds = await listCredentials();
        setCredentials(creds);
      }
    } catch {
      // not authenticated or error
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate() {
    setError("");
    setSaving(true);
    try {
      await createCredential({
        provider: selectedProvider,
        label,
        credentials: fieldValues,
      });
      setShowForm(false);
      setSelectedProvider("");
      setLabel("");
      setFieldValues({});
      await loadData();
    } catch (e: any) {
      setError(e.message || "Failed to save credential");
    } finally {
      setSaving(false);
    }
  }

  async function handleValidate(id: string) {
    setValidating(id);
    try {
      await validateCredential(id);
      await loadData();
    } catch {
      // error handled by reload
    } finally {
      setValidating(null);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this credential? This cannot be undone.")) return;
    try {
      await deleteCredential(id);
      await loadData();
    } catch {
      // error
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-blue-500" />
      </div>
    );
  }

  if (tier !== "enterprise") {
    return (
      <div className="min-h-screen bg-gray-950 text-white p-8">
        <div className="max-w-2xl mx-auto text-center mt-20">
          <div className="text-6xl mb-4">🔒</div>
          <h1 className="text-3xl font-bold mb-4">Enterprise Feature</h1>
          <p className="text-gray-400 mb-8">
            Cloud credential management and managed deployments require an Enterprise subscription.
          </p>
          <button
            onClick={() => router.push("/pricing")}
            className="px-6 py-3 bg-purple-600 hover:bg-purple-700 rounded-lg font-medium"
          >
            View Pricing Plans
          </button>
        </div>
      </div>
    );
  }

  const provider = PROVIDERS.find((p) => p.id === selectedProvider);

  return (
    <div className="min-h-screen bg-gray-950 text-white p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold">Cloud Credentials</h1>
            <p className="text-gray-400 mt-1">
              Manage encrypted cloud provider credentials for managed deployments
            </p>
          </div>
          {!showForm && (
            <button
              onClick={() => setShowForm(true)}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg font-medium"
            >
              + Add Credential
            </button>
          )}
        </div>

        {/* Add Credential Form */}
        {showForm && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-8">
            <h2 className="text-xl font-semibold mb-4">Add Cloud Credential</h2>

            {/* Provider Selection */}
            {!selectedProvider ? (
              <div className="grid grid-cols-3 gap-4">
                {PROVIDERS.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => setSelectedProvider(p.id)}
                    className="p-4 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg text-center"
                  >
                    <div className="text-3xl mb-2">{p.icon}</div>
                    <div className="font-medium">{p.name}</div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-sm text-gray-400 mb-4">
                  <span>{provider?.icon}</span>
                  <span>{provider?.name}</span>
                  <button
                    onClick={() => { setSelectedProvider(""); setFieldValues({}); }}
                    className="ml-auto text-blue-400 hover:text-blue-300"
                  >
                    Change provider
                  </button>
                </div>

                <div>
                  <label className="block text-sm text-gray-400 mb-1">Label</label>
                  <input
                    type="text"
                    value={label}
                    onChange={(e) => setLabel(e.target.value)}
                    placeholder="e.g., Production AWS, Dev GCP..."
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
                  />
                </div>

                {provider?.fields.map((field) => (
                  <div key={field.key}>
                    <label className="block text-sm text-gray-400 mb-1">{field.label}</label>
                    {field.multiline ? (
                      <textarea
                        value={fieldValues[field.key] || ""}
                        onChange={(e) =>
                          setFieldValues({ ...fieldValues, [field.key]: e.target.value })
                        }
                        placeholder={field.placeholder}
                        rows={5}
                        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white font-mono text-sm"
                      />
                    ) : (
                      <input
                        type={field.secret ? "password" : "text"}
                        value={fieldValues[field.key] || ""}
                        onChange={(e) =>
                          setFieldValues({ ...fieldValues, [field.key]: e.target.value })
                        }
                        placeholder={field.placeholder}
                        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
                      />
                    )}
                  </div>
                ))}

                {error && (
                  <div className="text-red-400 text-sm bg-red-900/20 border border-red-800 rounded-lg p-3">
                    {error}
                  </div>
                )}

                <div className="flex gap-3 pt-2">
                  <button
                    onClick={handleCreate}
                    disabled={saving || !label}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg font-medium"
                  >
                    {saving ? "Saving..." : "Save Credential"}
                  </button>
                  <button
                    onClick={() => { setShowForm(false); setSelectedProvider(""); setFieldValues({}); setError(""); }}
                    className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Existing Credentials */}
        {credentials.length === 0 && !showForm ? (
          <div className="text-center py-16 text-gray-500">
            <div className="text-5xl mb-4">🔐</div>
            <p className="text-lg">No cloud credentials stored yet</p>
            <p className="text-sm mt-1">Add credentials to enable managed cloud deployments</p>
          </div>
        ) : (
          <div className="space-y-4">
            {credentials.map((cred) => {
              const provInfo = PROVIDERS.find((p) => p.id === cred.provider);
              return (
                <div
                  key={cred.id}
                  className="bg-gray-900 border border-gray-800 rounded-xl p-5"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">{provInfo?.icon || "☁️"}</span>
                      <div>
                        <h3 className="font-semibold">{cred.label}</h3>
                        <p className="text-sm text-gray-400">
                          {provInfo?.name || cred.provider.toUpperCase()}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium ${
                          cred.status === "valid"
                            ? "bg-green-900/50 text-green-400"
                            : cred.status === "invalid"
                            ? "bg-red-900/50 text-red-400"
                            : cred.status === "expired"
                            ? "bg-yellow-900/50 text-yellow-400"
                            : "bg-gray-800 text-gray-400"
                        }`}
                      >
                        {cred.status.toUpperCase()}
                      </span>
                    </div>
                  </div>

                  {/* Masked fields */}
                  <div className="mt-3 bg-gray-800 rounded-lg p-3 font-mono text-sm text-gray-400">
                    {Object.entries(cred.masked_credentials).map(([k, v]) => (
                      <div key={k}>
                        <span className="text-gray-500">{k}:</span> {v}
                      </div>
                    ))}
                  </div>

                  <div className="flex gap-2 mt-4">
                    <button
                      onClick={() => handleValidate(cred.id)}
                      disabled={validating === cred.id}
                      className="px-3 py-1.5 bg-green-600/20 text-green-400 hover:bg-green-600/30 rounded-lg text-sm"
                    >
                      {validating === cred.id ? "Validating..." : "Validate"}
                    </button>
                    <button
                      onClick={() => handleDelete(cred.id)}
                      className="px-3 py-1.5 bg-red-600/20 text-red-400 hover:bg-red-600/30 rounded-lg text-sm"
                    >
                      Delete
                    </button>
                    {cred.validated_at && (
                      <span className="text-xs text-gray-500 self-center ml-auto">
                        Last validated: {new Date(cred.validated_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
