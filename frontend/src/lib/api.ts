import type {
  TokenResponse,
  PopularModel,
  LLMModel,
  CostEstimate,
  MultiCloudComparison,
  DeploymentConfig,
  Deployment,
  ChatResponse,
  UsageSummary,
} from "@/types";

const API_BASE = "/api";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Request failed: ${res.status}`);
  }

  return res.json();
}

// ── Auth ──
export async function register(
  email: string,
  password: string,
  fullName?: string
): Promise<TokenResponse> {
  const data = await request<TokenResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, full_name: fullName }),
  });
  localStorage.setItem("token", data.access_token);
  return data;
}

export async function login(
  email: string,
  password: string
): Promise<TokenResponse> {
  const data = await request<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  localStorage.setItem("token", data.access_token);
  return data;
}

export function logout(): void {
  localStorage.removeItem("token");
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

// ── Models ──
export async function getPopularModels(): Promise<PopularModel[]> {
  return request<PopularModel[]>("/models/popular");
}

export async function addHuggingFaceModel(data: {
  huggingface_id: string;
  precision?: string;
  context_length?: number;
}): Promise<LLMModel> {
  return request<LLMModel>("/models/huggingface", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function addCustomModel(data: {
  name: string;
  file_size_bytes: number;
  precision?: string;
  context_length?: number;
  parameters_billion?: number;
}): Promise<LLMModel> {
  return request<LLMModel>("/models/upload", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listModels(): Promise<LLMModel[]> {
  return request<LLMModel[]>("/models/");
}

export async function getModel(id: string): Promise<LLMModel> {
  return request<LLMModel>(`/models/${id}`);
}

// ── Cost Estimation ──
export async function estimateCost(data: {
  model_id: string;
  cloud_provider: string;
  expected_qps?: number;
  avg_tokens_per_request?: number;
  hours_per_day?: number;
  days_per_month?: number;
  autoscaling_enabled?: boolean;
  min_replicas?: number;
  max_replicas?: number;
}): Promise<CostEstimate> {
  return request<CostEstimate>("/estimate/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function compareProviders(
  modelId: string,
  qps?: number
): Promise<MultiCloudComparison> {
  const params = new URLSearchParams({ model_id: modelId });
  if (qps) params.set("expected_qps", String(qps));
  return request<MultiCloudComparison>(`/estimate/compare?${params}`);
}

// ── Public Cost Estimation (no auth) ──
export async function publicEstimateCost(data: {
  model_name: string;
  parameters_billion: number;
  precision: string;
  context_length: number;
  cloud_provider: string;
  expected_qps?: number;
  avg_tokens_per_request?: number;
  hours_per_day?: number;
  days_per_month?: number;
  autoscaling_enabled?: boolean;
}): Promise<CostEstimate> {
  return request<CostEstimate>("/estimate/public", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function publicCompareProviders(params: {
  parameters_billion: number;
  model_name?: string;
  precision?: string;
  context_length?: number;
  expected_qps?: number;
  hours_per_day?: number;
  days_per_month?: number;
}): Promise<MultiCloudComparison> {
  const qs = new URLSearchParams({
    parameters_billion: String(params.parameters_billion),
    model_name: params.model_name || "Custom Model",
    precision: params.precision || "fp16",
    context_length: String(params.context_length || 4096),
    expected_qps: String(params.expected_qps || 1),
    hours_per_day: String(params.hours_per_day || 24),
    days_per_month: String(params.days_per_month || 30),
  });
  return request<MultiCloudComparison>(`/estimate/public/compare?${qs}`, {
    method: "POST",
  });
}

// ── API Provider Comparison ──
export async function compareWithAPIProviders(data: {
  model_name: string;
  parameters_billion: number;
  precision: string;
  context_length: number;
  cloud_provider: string;
  expected_qps?: number;
  avg_tokens_per_request?: number;
  hours_per_day?: number;
  days_per_month?: number;
  autoscaling_enabled?: boolean;
}): Promise<import("@/types").APIProviderComparison> {
  return request<import("@/types").APIProviderComparison>(
    "/estimate/public/compare-api-providers",
    { method: "POST", body: JSON.stringify(data) }
  );
}

// ── Pricing Status ──
export async function getPricingStatus(): Promise<
  import("@/types").PricingStatus
> {
  return request<import("@/types").PricingStatus>("/pricing/status");
}

// ── Deployment ──
export async function generateDeployConfigs(data: {
  model_id: string;
  cloud_provider: string;
  region?: string;
}): Promise<DeploymentConfig> {
  return request<DeploymentConfig>("/deploy/generate-configs", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function generateDeployFromConfig(data: {
  config_id: string;
  cloud_provider: string;
  region?: string;
  instance_type?: string;
  gpu_type?: string;
  gpu_count?: number;
}): Promise<DeploymentConfig> {
  return request<DeploymentConfig>("/deploy/from-config", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getDeployBundleUrl(deploymentId: string): string {
  return `${API_BASE}/deploy/${deploymentId}/bundle`;
}

export async function listDeployments(): Promise<Deployment[]> {
  return request<Deployment[]>("/deploy/list");
}

export async function startDeployment(id: string): Promise<Deployment> {
  return request<Deployment>(`/deploy/${id}/start`, { method: "POST" });
}

// ── Chat ──
export async function sendMessage(data: {
  deployment_id: string;
  message: string;
  max_tokens?: number;
  temperature?: number;
}): Promise<ChatResponse> {
  return request<ChatResponse>("/chat/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ── Usage ──
export async function getUsage(deploymentId: string): Promise<UsageSummary> {
  return request<UsageSummary>(`/chat/usage/${deploymentId}`);
}

// ── Subscription ──
export async function getSubscriptionStatus(): Promise<
  import("@/types").SubscriptionStatus
> {
  return request<import("@/types").SubscriptionStatus>("/subscription/status");
}

export async function upgradeSubscription(
  targetTier: string
): Promise<{ message: string; tier: string; features: string[] }> {
  return request("/subscription/upgrade", {
    method: "POST",
    body: JSON.stringify({ target_tier: targetTier }),
  });
}

export async function createCheckoutSession(
  targetTier: string
): Promise<import("@/types").CheckoutResponse> {
  return request("/subscription/create-checkout", {
    method: "POST",
    body: JSON.stringify({ target_tier: targetTier }),
  });
}

export async function createPortalSession(): Promise<
  import("@/types").PortalResponse
> {
  return request("/subscription/create-portal", { method: "POST" });
}

// ── Model Builder ──
export async function createModelConfig(data: {
  name: string;
  description?: string;
  base_model_id?: string;
  base_model_hf_id?: string;
  adapter_hf_id?: string;
  is_merge?: boolean;
  merge_method?: string;
  merge_models?: { model_hf_id: string; weight: number }[];
  quantization_method?: string;
  system_prompt?: string;
  default_temperature?: number;
  default_top_p?: number;
  default_max_tokens?: number;
}): Promise<import("@/types").ModelConfig> {
  return request("/builder/configs", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listModelConfigs(): Promise<
  import("@/types").ModelConfig[]
> {
  return request("/builder/configs");
}

export async function getModelConfig(
  id: string
): Promise<import("@/types").ModelConfig> {
  return request(`/builder/configs/${id}`);
}

export async function updateModelConfig(
  id: string,
  data: Record<string, any>
): Promise<import("@/types").ModelConfig> {
  return request(`/builder/configs/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteModelConfig(id: string): Promise<void> {
  return request(`/builder/configs/${id}`, { method: "DELETE" });
}

export async function calculateConfigSpecs(
  id: string
): Promise<import("@/types").SpecsCalculation> {
  return request(`/builder/configs/${id}/calculate-specs`, { method: "POST" });
}

export async function saveConfigVersion(
  id: string,
  changeSummary?: string
): Promise<import("@/types").ModelConfigVersion> {
  const qs = changeSummary
    ? `?change_summary=${encodeURIComponent(changeSummary)}`
    : "";
  return request(`/builder/configs/${id}/save-version${qs}`, {
    method: "POST",
  });
}

export async function listConfigVersions(
  id: string
): Promise<import("@/types").ModelConfigVersion[]> {
  return request(`/builder/configs/${id}/versions`);
}

export async function promoteConfigToModel(
  id: string
): Promise<{ message: string; model_id: string }> {
  return request(`/builder/configs/${id}/to-model`, { method: "POST" });
}

export async function searchHFModels(
  query: string
): Promise<import("@/types").HFModelResult[]> {
  return request(`/builder/models/search?q=${encodeURIComponent(query)}`);
}

export async function searchHFAdapters(
  query: string
): Promise<import("@/types").HFAdapterResult[]> {
  return request(`/builder/adapters/search?q=${encodeURIComponent(query)}`);
}

// ── Cloud Credentials ──

export async function getProviderFields(): Promise<
  import("@/types").ProviderFields[]
> {
  return request("/credentials/providers");
}

export async function createCredential(data: {
  provider: string;
  label: string;
  credentials: Record<string, string>;
}): Promise<import("@/types").CloudCredential> {
  return request("/credentials/create", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listCredentials(): Promise<
  import("@/types").CloudCredential[]
> {
  return request("/credentials/list");
}

export async function validateCredential(
  id: string
): Promise<{ valid: boolean; message: string; status: string }> {
  return request(`/credentials/${id}/validate`, { method: "POST" });
}

export async function deleteCredential(id: string): Promise<void> {
  return request(`/credentials/${id}`, { method: "DELETE" });
}

// ── Managed Deployments ──

export async function createManagedDeployment(data: {
  deployment_id: string;
  credential_id: string;
  autoscaling_enabled?: boolean;
  min_replicas?: number;
  max_replicas?: number;
  target_gpu_utilization?: number;
}): Promise<import("@/types").ManagedDeployment> {
  return request("/managed/deploy", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listManagedDeployments(): Promise<
  import("@/types").ManagedDeployment[]
> {
  return request("/managed/list");
}

export async function getManagedDeployment(
  id: string
): Promise<import("@/types").ManagedDeployment> {
  return request(`/managed/${id}`);
}

export async function getManagedMetrics(
  id: string,
  hours?: number
): Promise<import("@/types").DeploymentMetrics> {
  const qs = hours ? `?hours=${hours}` : "";
  return request(`/managed/${id}/metrics${qs}`);
}

export async function scaleManagedDeployment(
  id: string,
  data: {
    min_replicas?: number;
    max_replicas?: number;
    target_gpu_utilization?: number;
    autoscaling_enabled?: boolean;
  }
): Promise<any> {
  return request(`/managed/${id}/scale`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function stopManagedDeployment(id: string): Promise<any> {
  return request(`/managed/${id}/stop`, { method: "POST" });
}

export async function startManagedDeployment(id: string): Promise<any> {
  return request(`/managed/${id}/start`, { method: "POST" });
}

export async function teardownManagedDeployment(id: string): Promise<any> {
  return request(`/managed/${id}/teardown`, { method: "POST" });
}

// ── Analytics ──

export async function getAnalyticsSummary(): Promise<any> {
  return request("/analytics/summary");
}

export async function getUsageSeries(days?: number): Promise<any[]> {
  const qs = days ? `?days=${days}` : "";
  return request(`/analytics/usage-series${qs}`);
}

export async function getCostBreakdown(): Promise<any[]> {
  return request("/analytics/cost-breakdown");
}

// ── Playground ──

export async function simulatePlayground(data: {
  config_id: string;
  prompt: string;
}): Promise<any> {
  return request("/playground/simulate", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ── Cost Alerts ──

export async function createCostAlert(data: {
  managed_deployment_id: string;
  monthly_budget_usd: number;
  alert_threshold_pct: number;
}): Promise<any> {
  return request("/alerts/create", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listCostAlerts(): Promise<any[]> {
  return request("/alerts/list");
}

export async function updateCostAlert(
  id: string,
  data: { monthly_budget_usd?: number; alert_threshold_pct?: number }
): Promise<any> {
  return request(`/alerts/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteCostAlert(id: string): Promise<void> {
  return request(`/alerts/${id}`, { method: "DELETE" });
}
