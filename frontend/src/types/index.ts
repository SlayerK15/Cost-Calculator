export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface PopularModel {
  id: string;
  name: string;
  organization: string;
  parameters_billion: number;
  architecture: string;
  context_length: number;
}

export interface LLMModel {
  id: string;
  name: string;
  source: "huggingface" | "custom_upload";
  huggingface_id: string | null;
  file_size_bytes: number | null;
  parameters_billion: number | null;
  precision: string;
  context_length: number;
  architecture: string | null;
  is_parameters_estimated: boolean;
  profiled: boolean;
  peak_vram_gb: number | null;
  tokens_per_second: number | null;
  created_at: string;
}

export interface GPURecommendation {
  gpu_type: string;
  gpu_count: number;
  instance_type: string;
  vram_per_gpu_gb: number;
  total_vram_gb: number;
  cost_per_hour: number;
}

export interface CostBreakdown {
  compute_cost_monthly: number;
  storage_cost_monthly: number;
  bandwidth_cost_monthly: number;
  idle_cost_monthly: number;
  kv_cache_overhead_cost: number;
  total_cost_monthly: number;
}

export interface ScalingScenario {
  name: string;
  description: string;
  replicas: number;
  total_monthly_cost: number;
  cost_per_request: number;
}

export interface CostEstimate {
  id: string;
  model_name: string;
  cloud_provider: string;
  vram_required_gb: number;
  recommended_gpu: GPURecommendation;
  cost_breakdown: CostBreakdown;
  scaling_scenarios: ScalingScenario[];
  optimized_config: Record<string, any> | null;
  recommendation: string;
}

export interface MultiCloudComparison {
  model_id: string;
  model_name: string;
  estimates: CostEstimate[];
}

export interface DeploymentConfig {
  deployment_id: string;
  dockerfile: string;
  kubernetes_yaml: string;
  terraform_config: string;
  ci_cd_pipeline: string;
  cloudformation: string;
  quickstart: string;
  merge_config: string;
}

export interface Deployment {
  id: string;
  model_id: string;
  cloud_provider: string;
  status: string;
  instance_type: string;
  gpu_type: string;
  gpu_count: number;
  region: string;
  endpoint_url: string | null;
  total_requests: number;
  total_tokens_generated: number;
  total_cost_incurred: number;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  message: ChatMessage;
  tokens_used: number;
  latency_ms: number;
}

export interface UsageSummary {
  deployment_id: string;
  total_requests: number;
  total_tokens_input: number;
  total_tokens_output: number;
  total_cost_usd: number;
  avg_latency_ms: number;
  requests_today: number;
  cost_today: number;
}

export interface APIProviderPlan {
  provider: string;
  model: string;
  input_cost_per_million: number;
  output_cost_per_million: number;
  monthly_cost: number;
  cost_per_request: number;
}

export interface APIProviderComparison {
  monthly_requests: number;
  monthly_input_tokens: number;
  monthly_output_tokens: number;
  avg_input_tokens_per_request: number;
  avg_output_tokens_per_request: number;
  api_providers: APIProviderPlan[];
  self_hosted_monthly: number;
  self_hosted_provider: string;
}

export interface PricingStatus {
  gpu_prices_count: number;
  api_prices_count: number;
  gpu_last_updated: string | null;
  api_last_updated: string | null;
  using_live_prices: boolean;
}

// ── Subscription ──

export interface SubscriptionStatus {
  tier: "free" | "pro" | "enterprise";
  expires_at: string | null;
  features: string[];
  has_payment_method: boolean;
  stripe_subscription_id: string | null;
}

export interface CheckoutResponse {
  checkout_url: string;
}

export interface PortalResponse {
  portal_url: string;
}

// ── Model Builder ──

export interface MergeModelEntry {
  model_hf_id: string;
  weight: number;
}

export interface ModelConfig {
  id: string;
  name: string;
  description: string | null;
  version: number;
  base_model_id: string | null;
  base_model_hf_id: string | null;
  adapter_hf_id: string | null;
  is_merge: boolean;
  merge_method: string | null;
  merge_models_json: MergeModelEntry[] | null;
  quantization_method: string;
  system_prompt: string | null;
  default_temperature: number;
  default_top_p: number;
  default_max_tokens: number;
  effective_parameters_billion: number | null;
  effective_precision: string | null;
  effective_context_length: number | null;
  estimated_vram_gb: number | null;
  pipeline_json: Record<string, any> | null;
  created_at: string;
  updated_at: string;
}

export interface ModelConfigVersion {
  id: string;
  config_id: string;
  version: number;
  snapshot_json: Record<string, any>;
  change_summary: string | null;
  created_at: string;
}

export interface SpecsCalculation {
  effective_parameters_billion: number;
  effective_precision: string;
  effective_context_length: number;
  estimated_vram_gb: number;
  adapter_overhead_gb: number;
  base_vram_gb: number;
}

export interface HFModelResult {
  model_id: string;
  name: string;
  author: string | null;
  downloads: number;
  likes: number;
  pipeline_tag: string | null;
}

export interface HFAdapterResult {
  adapter_id: string;
  name: string;
  author: string | null;
  base_model: string | null;
  downloads: number;
  likes: number;
}

// ── Managed Cloud Deployment (Phase 3) ──

export interface CloudCredential {
  id: string;
  provider: string;
  label: string;
  status: "pending" | "valid" | "invalid" | "expired";
  masked_credentials: Record<string, string>;
  validated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProviderFields {
  provider: string;
  required_fields: string[];
}

export interface ManagedDeployment {
  id: string;
  deployment_id: string | null;
  credential_id: string;
  status: string;
  cloud_provider: string;
  region: string;
  instance_type: string;
  gpu_type: string;
  gpu_count: number;
  cluster_endpoint: string | null;
  autoscaling_enabled: boolean;
  min_replicas: number;
  max_replicas: number;
  target_gpu_utilization: number;
  health_status: string;
  estimated_hourly_cost: number;
  total_cost_incurred: number;
  uptime_seconds: number;
  created_at: string;
  updated_at: string;
}

export interface ScalingEvent {
  timestamp: string;
  event: "scale_up" | "scale_down";
  reason: string;
  from_replicas: number;
  to_replicas: number;
  gpu_utilization: number;
}

export interface DeploymentMetrics {
  current: {
    requests_count: number;
    avg_latency_ms: number;
    p99_latency_ms: number;
    tokens_generated: number;
    gpu_utilization: number;
    vram_used_gb: number;
    cpu_utilization: number;
    active_replicas: number;
    cost_usd: number;
  };
  time_series: Array<{
    timestamp: string;
    requests_count: number;
    avg_latency_ms: number;
    p99_latency_ms: number;
    tokens_generated: number;
    gpu_utilization: number;
    vram_used_gb: number;
    cpu_utilization: number;
    active_replicas: number;
    cost_usd: number;
  }>;
  summary: {
    total_requests: number;
    total_tokens: number;
    total_cost_usd: number;
    avg_latency_ms: number;
    avg_gpu_utilization: number;
    uptime_hours: number;
  };
  scaling_events: ScalingEvent[];
}

// ── Cost Alerts (Phase 5B) ──

export interface CostAlert {
  id: string;
  managed_deployment_id: string;
  monthly_budget_usd: number;
  alert_threshold_pct: number;
  current_spend_usd: number;
  alert_triggered: boolean;
  alert_triggered_at: string | null;
  created_at: string;
  updated_at: string;
}

// ── Playground (Phase 5A) ──

export interface PlaygroundResponse {
  response_text: string;
  tokens_used: number;
  estimated_latency_ms: number;
  estimated_cost_per_request: number;
  model_info: {
    name: string;
    parameters_billion: number | null;
    quantization: string;
    context_length: number;
  };
}

// ── Phase 6: Comparison & Sharing ──

export interface CompareModelEntry {
  name: string;
  parameters_billion: number;
  precision: string;
  context_length: number;
}

export interface ModelComparisonEntry {
  model_name: string;
  parameters_billion: number;
  precision: string;
  vram_required_gb: number;
  gpu_type: string;
  gpu_count: number;
  instance_type: string;
  cost_per_hour: number;
  total_cost_monthly: number;
  compute_cost_monthly: number;
  storage_cost_monthly: number;
  recommendation: string;
}

export interface CompareModelsResponse {
  cloud_provider: string;
  comparisons: ModelComparisonEntry[];
}

export interface SharedEstimateData {
  share_token: string;
  estimate: Record<string, any>;
  api_comparison: Record<string, any> | null;
  model_name: string;
  cloud_provider: string;
  total_cost_monthly: number;
  views_count: number;
  created_at: string;
}

export interface SavedEstimateItem {
  id: string;
  label: string;
  model_name: string;
  cloud_provider: string;
  total_cost_monthly: number;
  parameters_billion: number | null;
  created_at: string;
}

// ── Phase 7: Intelligence ──

export interface RecommendationResult {
  model_name: string;
  parameters_billion: number;
  quality_tier: string;
  tags: string[];
  cloud_provider: string;
  instance_type: string;
  gpu_type: string;
  gpu_count: number;
  vram_required_gb: number;
  monthly_cost: number;
  recommendation: string;
}

export interface RecommendResponse {
  use_case: string;
  budget: number;
  results: RecommendationResult[];
}

export interface OptimizationSuggestion {
  type: string;
  title: string;
  description: string;
  current_cost: number;
  optimized_cost: number;
  savings_monthly: number;
  savings_pct: number;
  tradeoff: string;
}

export interface OptimizationReport {
  current_monthly_cost: number;
  optimizations: OptimizationSuggestion[];
  total_potential_savings: number;
  best_optimized_cost: number;
}

export interface ForecastDay {
  date: string;
  projected_cost: number;
}

export interface ForecastResult {
  projected_monthly_cost: number;
  current_monthly_cost: number;
  change_pct: number;
  daily_forecast: ForecastDay[];
  confidence: string;
}

// ── Infrastructure Agent ──

export interface InfraFileEntry {
  filename: string;
  content: string;
  language: string;
}

export interface InfraGenerateResponse {
  deployment_id: string;
  cloud_provider: string;
  iac_language: string;
  region: string;
  instance_type: string;
  gpu_type: string;
  gpu_count: number;
  estimated_monthly_cost: number;
  files: InfraFileEntry[];
  quickstart: string;
  summary: string;
}

export interface InfraSearchResult {
  source: string;
  title: string;
  snippet: string;
  relevance: number;
}

export interface InfraSearchResponse {
  query: string;
  results: InfraSearchResult[];
}

// ── Phase 8: Agent Chatbot ──

export interface AgentMessage {
  role: "user" | "assistant";
  content: string;
}
