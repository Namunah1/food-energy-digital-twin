const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${path} failed: ${res.status} ${text}`);
  }
  return res.json();
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${path} failed: ${res.status} ${text}`);
  }
  return res.json();
}

export function wsURL(path: string) {
  const wsBase = API_BASE.replace(/^http/, "ws");
  return `${wsBase}${path}`;
}

// ── Types (mirrors app/schemas.py + model_bridge return shapes) ────────────

export interface CountryListItem {
  id: string;
  name: string;
  type: string;
  lat: number;
  lon: number;
  region: string;
  population: number;
}

export interface NodeState {
  id: string;
  name: string;
  lat: number;
  lon: number;
  region: string;
  food_security: number;
  export_ban: boolean;
  export_fraction: number;
  population_millions: number;
  undernourished: boolean;
  capital_bn: number;
  technology: number;
  energy_fuel: number;
  energy_stress: number;
  fs_index: number;
  cc_index: number;
  overload_food: boolean;
}

export interface NetworkEdge {
  source: string;
  target: string;
  active: boolean;
  capacity: number;
  cost: number;
  risk: number;
}

export interface MetricsRecord {
  [key: string]: number;
  step: number;
  U_undernourished: number;
  GFS: number;
  TC_trade_collapse: number;
  EB_export_ban_rate: number;
  PAR_millions: number;
  famine_deaths_step: number;
  price_index: number;
  price_ratio: number;
  SAV_scale: number;
  SAV_homogeneity: number;
  SAV_connectivity: number;
  SAV_power: number;
  mean_FS_index: number;
  mean_ES_index: number;
  n_overload_food: number;
  n_overload_energy: number;
  total_supply_kcal_yr: number;
  total_demand_kcal_yr: number;
  trade_volume_kcal: number;
}

export interface ScenarioSpec {
  name: string;
  label: string;
  description: string;
  storyline: string;
  trade_offs: string;
  triggers: Record<string, unknown>[];
  has_response: boolean;
}

export interface CountryProfile {
  id: string;
  name: string;
  type: string;
  lat: number;
  lon: number;
  region: string;
  population: number;
  capital_bn: number;
  gdp_bn: number;
  technology: number;
  energy_fuel: number;
  energy_renew: number;
  energy_stress_index: number;
  food_security: number;
  undernourished: boolean;
  export_ban: boolean;
  export_fraction: number;
  FS_index: number;
  CC_index: number;
  overload_food: boolean;
  climate_vuln: number;
  political_risk: number;
  exports_this_step: number;
  imports_this_step: number;
  trade_partners_export: { partner: string; direction: string; active: boolean; capacity: number }[];
  trade_partners_import: { partner: string; direction: string; active: boolean; capacity: number }[];
}

export interface ShockInput {
  shock_type:
    | "climate_drought"
    | "energy_crisis"
    | "pandemic"
    | "financial_crisis"
    | "export_ban"
    | "war"
    | "fertilizer_shortage"
    | "shipping_disruption"
    | "currency_collapse";
  start_step: number;
  duration: number;
  severity: number;
  scope: number;
  target_node?: string | null;
}

export interface SimulationRequest {
  shocks: ShockInput[];
  responses: string[];
  n_steps: number;
  seed: number;
  compare_baseline: boolean;
  capture_snapshots?: boolean;
}

export interface SimulationSnapshot {
  step: number;
  year: number;
  nodes: NodeState[];
}

export interface SimulationResult {
  summary: Record<string, number | string>;
  timeseries: MetricsRecord[];
  nodes: NodeState[];
  snapshots?: SimulationSnapshot[] | null;
  attribution: Record<string, number | string>[];
  triggers_applied: Record<string, unknown>[];
  baseline?: {
    summary: Record<string, number | string>;
    timeseries: MetricsRecord[];
    nodes: NodeState[];
  };
}

// ── API functions ───────────────────────────────────────────────────────────

export interface HistoricalEpisodeListItem {
  key: string;
  label: string;
  trigger_calendar_year: number;
  scored: boolean;
}

export interface HistoricalEpisodeResult {
  key: string;
  label: string;
  trigger_calendar_year: number;
  init_year: number;
  triggers: Record<string, unknown>[];
  timeseries: MetricsRecord[];
  nodes: NodeState[];
  descriptive_only?: boolean;
  // present only when descriptive_only is true:
  note?: string;
  model_max_price_index?: number;
  model_max_PAR_millions?: number;
  model_max_n_overload_food?: number;
  real_par_niger_millions?: string;
  // present only when descriptive_only is false/absent:
  scored?: {
    real_fpi: number;
    model_fpi_mean: number;
    model_fpi_std: number;
    fpi_error_pct: number;
    real_eb_rate: number;
    model_eb_mean: number;
    real_par_bn: number;
    model_par_bn: number;
    par_ratio: number;
    score1_fpi: boolean;
    score2_eb: boolean;
    score4_par: boolean;
    score5_hd_props: boolean;
    crisis_properties: Record<string, boolean>;
    n_LFBB_events: number;
  };
}

export const api = {
  health: () => getJSON<{ status: string }>("/api/health"),
  countries: () => getJSON<CountryListItem[]>("/api/countries"),
  scenarios: () => getJSON<ScenarioSpec[]>("/api/scenarios"),
  baselineMetrics: (steps = 10) =>
    getJSON<{ timeseries: MetricsRecord[]; summary: Record<string, number>; current: MetricsRecord }>(
      `/api/baseline/metrics?steps=${steps}`
    ),
  baselineNodes: (steps = 10) => getJSON<NodeState[]>(`/api/baseline/nodes?steps=${steps}`),
  network: (steps = 10) => getJSON<{ nodes: NodeState[]; edges: NetworkEdge[] }>(`/api/network?steps=${steps}`),
  country: (name: string, steps = 10) =>
    getJSON<CountryProfile>(`/api/country/${encodeURIComponent(name)}?steps=${steps}`),
  runSimulation: (req: SimulationRequest) => postJSON<SimulationResult>("/api/run_simulation", req),
  researchScenario: (name: string, n_mc = 5, n_steps = 30, seed = 42) =>
    postJSON("/api/research_scenario", { name, n_mc, n_steps, seed }),
  historicalEpisodes: () => getJSON<HistoricalEpisodeListItem[]>("/api/historical/episodes"),
  historicalEpisode: (key: string, n_mc = 6, n_steps = 25) =>
    getJSON<HistoricalEpisodeResult>(`/api/historical/${key}?n_mc=${n_mc}&n_steps=${n_steps}`),
};

export { API_BASE };

export interface ComparisonRunSpec {
  kind: "research" | "custom";
  name?: string;
  id?: string;
  label?: string;
  shocks?: ShockInput[];
  responses?: string[];
}

export interface ComparisonRunResult {
  id: string;
  label: string;
  kind: "research" | "custom";
  summary: Record<string, number | string>;
  timeseries: MetricsRecord[];
  nodes: NodeState[];
}

export interface ComparisonResult {
  runs: ComparisonRunResult[];
}

export async function runComparison(
  runs: ComparisonRunSpec[],
  n_steps = 25,
  seed = 42
): Promise<ComparisonResult> {
  const res = await fetch(`${API_BASE}/api/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ runs, n_steps, seed }),
  });
  if (!res.ok) throw new Error(`compare failed: ${res.status} ${await res.text()}`);
  return res.json();
}

export interface NodeWithCentrality extends NodeState {
  degree_centrality: number;
  in_degree_centrality: number;
  out_degree_centrality: number;
  eigenvector_centrality: number;
  betweenness_centrality: number;
  in_degree: number;
  out_degree: number;
}

export async function fetchNetworkCentrality(steps = 10): Promise<{ nodes: NodeWithCentrality[]; edges: NetworkEdge[] }> {
  const res = await fetch(`${API_BASE}/api/network/centrality?steps=${steps}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`centrality failed: ${res.status}`);
  return res.json();
}

export interface TimeMachineSnapshot {
  year: number;
  observed: boolean;
  nodes: NodeState[];
}

export interface TimeMachineResult {
  init_year: number;
  end_year: number;
  data_horizon_year: number;
  timeseries: MetricsRecord[];
  snapshots: TimeMachineSnapshot[];
}

export async function fetchTimeMachine(end_year = 2050): Promise<TimeMachineResult> {
  const res = await fetch(`${API_BASE}/api/time_machine?end_year=${end_year}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`time_machine failed: ${res.status}`);
  return res.json();
}

export interface AdvisorProvider {
  name: string;
  configured: boolean;
}

export interface AdvisorAnswer {
  answer: string;
  provider: string;
  provider_error?: string;
  grounding: { intent: string; data: Record<string, unknown> };
}

export async function fetchAdvisorProviders(): Promise<AdvisorProvider[]> {
  const res = await fetch(`${API_BASE}/api/advisor/providers`, { cache: "no-store" });
  if (!res.ok) throw new Error("providers fetch failed");
  return res.json();
}

export async function askAdvisor(question: string): Promise<AdvisorAnswer> {
  const res = await fetch(`${API_BASE}/api/advisor/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error(`advisor failed: ${res.status} ${await res.text()}`);
  return res.json();
}

export interface MCStat {
  mean: number;
  std: number;
  p5: number;
  p95: number;
}

export interface ProjectionResult {
  start_year: number;
  target_year: number;
  n_steps: number;
  n_mc: number;
  used_real_anchor: boolean;
  stats: Record<string, MCStat>;
  baseline_summary: Record<string, number | string>;
  timeseries: MetricsRecord[];
  nodes: NodeState[];
  attribution: Record<string, number | string>[];
  triggers_applied: Record<string, unknown>[];
  explanation: string | null;
  explanation_provider: string | null;
}

export interface ProjectionRequestBody {
  shocks: ShockInput[];
  responses: string[];
  target_year: number;
  start_year?: number | null;
  n_mc?: number;
  seed?: number;
  explain?: boolean;
}

export async function runProjection(body: ProjectionRequestBody): Promise<ProjectionResult> {
  const res = await fetch(`${API_BASE}/api/project`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`project failed: ${res.status} ${await res.text()}`);
  return res.json();
}

export interface ShockLibraryEntry {
  label: string;
  description: string;
  affected_variables: string[];
  default_severity: number;
  default_scope: number;
  default_duration: number;
  recovery_model: string;
}

export async function fetchShockLibrary(): Promise<Record<string, ShockLibraryEntry>> {
  const res = await fetch(`${API_BASE}/api/shock_library`, { cache: "no-store" });
  if (!res.ok) throw new Error("shock library fetch failed");
  return res.json();
}

export interface CascadeEvent {
  node: string;
  step: number;
  year: number;
  is_origin: boolean;
  sigma_gap_vs_baseline: number;
}

export interface CascadeEdge {
  source: string;
  target: string;
  source_step: number;
  target_step: number;
  edge_capacity: number;
}

export interface CascadeTraceResult {
  start_year: number;
  n_steps: number;
  origin_nodes: string[];
  triggers_applied: Record<string, unknown>[];
  events: CascadeEvent[];
  cascade_edges: CascadeEdge[];
  total_affected: number;
  detection_method: string;
  final_summary_shocked: Record<string, number | string>;
  final_summary_baseline: Record<string, number | string>;
}

export interface CascadeTraceRequestBody {
  shocks: ShockInput[];
  responses: string[];
  start_year: number;
  n_steps: number;
  seed?: number;
}

export async function runCascadeTrace(body: CascadeTraceRequestBody): Promise<CascadeTraceResult> {
  const res = await fetch(`${API_BASE}/api/cascade_trace`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`cascade_trace failed: ${res.status} ${await res.text()}`);
  return res.json();
}

export interface PolicyRankRow {
  lever: string;
  label: string;
  max_price_index: number;
  max_PAR_millions: number;
  max_TC: number;
  max_n_overload_food: number;
  min_GFS: number;
  population_saved_millions: number;
  price_index_reduction: number;
  trade_collapse_reduction: number;
  food_security_improvement: number;
}

export interface PolicyOptimizationResult {
  start_year: number;
  n_steps: number;
  control_summary: Record<string, number | string>;
  ranked_policies: PolicyRankRow[];
  note: string;
}

export async function runPolicyOptimization(
  shocks: ShockInput[],
  start_year: number,
  n_steps: number
): Promise<PolicyOptimizationResult> {
  const res = await fetch(`${API_BASE}/api/policy_optimization`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ shocks, start_year, n_steps }),
  });
  if (!res.ok) throw new Error(`policy_optimization failed: ${res.status} ${await res.text()}`);
  return res.json();
}

// PHASE E (this session): client bindings for the Phase A/B/D
// /api/policy_search and /api/policy_search/node_level endpoints —
// extends the policy-optimization surface above (unchanged), rather than
// replacing it. Types mirror the Pydantic response shapes exactly
// (scenarios.py::policy_search / node_level_policy_search).

export interface CustomLeverSpec {
  type: string;
  node?: string;
  donor?: string;
  recipient?: string;
  target_nodes?: string[];
  aid_fraction?: number;
  export_fraction_cap?: number;
  effectiveness?: number;
  tariff_multiplier?: number;
  release_fraction?: number;
  mode?: string;
  support_level?: number;
  levy_threshold_margin?: number;
  levy_rate?: number;
}

export interface PolicySearchCandidate {
  label: string;
  params: Record<string, unknown>;
  max_price_index: number;
  max_PAR_millions: number;
  max_TC: number;
  max_n_overload_food: number;
  min_GFS: number;
  population_saved_millions: number;
  price_index_reduction: number;
  illustrative_cost?: number | null;
  within_budget?: boolean;
}

export interface PolicySearchResult {
  control_summary: Record<string, number | string>;
  ranked_policies: PolicySearchCandidate[];
  n_evaluated: number;
  search_space: {
    levers: string[];
    ranges: Record<string, [number, number]>;
    n_random_sampled: number;
    fixed_baselines_included: boolean;
    node_targeted_sampling: boolean;
  };
  max_budget: number | null;
  objective: string;
}

export interface PolicySearchRequestBody {
  shocks: ShockInput[];
  start_year: number;
  n_steps: number;
  n_random?: number;
  include_fixed_levers?: boolean;
  custom_levers?: CustomLeverSpec[];
  include_node_targeted_sampling?: boolean;
  node_pool?: string[];
  max_budget?: number;
  seed?: number;
}

export async function runPolicySearch(
  body: PolicySearchRequestBody
): Promise<PolicySearchResult> {
  return postJSON<PolicySearchResult>("/api/policy_search", body);
}

export interface NodeLevelSearchResult {
  control_summary: Record<string, number | string>;
  lever_type: string;
  ranked_targets: PolicySearchCandidate[];
  n_evaluated: number;
  max_budget: number | null;
  cost_model_note: string;
  objective: string;
}

export interface NodeLevelSearchRequestBody {
  lever_type: string;
  node_pool: string[];
  shocks: ShockInput[];
  start_year: number;
  n_steps: number;
  n_random?: number;
  max_budget?: number;
  seed?: number;
}

export async function runNodeLevelPolicySearch(
  body: NodeLevelSearchRequestBody
): Promise<NodeLevelSearchResult> {
  return postJSON<NodeLevelSearchResult>("/api/policy_search/node_level", body);
}

export interface CountryHistoryRow {
  [key: string]: number | boolean;
  year: number;
  food_security: number;
  technology: number;
  energy_stress: number;
  population_millions: number;
  capital_bn: number;
  undernourished: boolean;
  export_ban: boolean;
  overload_food: boolean;
}

export async function fetchCountryHistory(name: string): Promise<CountryHistoryRow[]> {
  const res = await fetch(`${API_BASE}/api/country/${encodeURIComponent(name)}/history`, { cache: "no-store" });
  if (!res.ok) throw new Error(`country history failed: ${res.status}`);
  return res.json();
}

// ── Experiment Studio (canonical API) ────────────────────────────────────────

export type ExperimentMode = "historical" | "counterfactual" | "projection";

export interface ExperimentSpec {
  label?: string | null;
  mode: ExperimentMode;
  anchor_year: number;
  target_year: number;
  known_episode?: string | null;
  shocks: ShockInput[];
  responses: string[];
  n_mc: number;
  seed: number;
  explain: boolean;
  evaluate_policies: boolean;
  target_country?: string | null;
  parent_id?: string | null;
  annotation?: string | null;
}

export interface ExperimentMetadata {
  id: string;
  label: string;
  mode: ExperimentMode;
  parent_id: string | null;
  created_at: string;
  annotation: string | null;
  target_country?: string | null;
}

export interface MCStatMap {
  [metric: string]: MCStat;
}

export interface CascadeResult {
  events: CascadeEvent[];
  total_affected: number;
}

export interface ExperimentResult {
  anchor_year: number;
  target_year: number;
  n_steps: number;
  summary: Record<string, number | string>;
  baseline_summary: Record<string, number | string>;
  timeseries: MetricsRecord[];
  baseline_timeseries: MetricsRecord[];
  snapshots: SimulationSnapshot[];
  nodes: NodeState[];
  triggers_applied: Record<string, unknown>[];
  origin_nodes: string[];
  cascade: CascadeResult | null;
  attribution: Record<string, number | string>[];
  uncertainty: MCStatMap | null;
  policy_rankings: PolicyOptimizationResult | null;
  episode_meta: Record<string, unknown>;
  explanation: string | null;
  explanation_provider: string | null;
}

export interface Experiment {
  metadata: ExperimentMetadata;
  spec: ExperimentSpec;
  result: ExperimentResult;
}

export interface ExperimentListItem {
  id: string;
  label: string;
  mode: ExperimentMode;
  parent_id: string | null;
  created_at: string;
  annotation: string | null;
}

export interface ExperimentCreateBody {
  label?: string | null;
  mode: ExperimentMode;
  anchor_year: number;
  target_year: number;
  known_episode?: string | null;
  shocks?: ShockInput[];
  responses?: string[];
  n_mc?: number;
  seed?: number;
  explain?: boolean;
  evaluate_policies?: boolean;
  target_country?: string | null;
  parent_id?: string | null;
  annotation?: string | null;
}

export async function createExperiment(body: ExperimentCreateBody): Promise<Experiment> {
  const res = await fetch(`${API_BASE}/api/experiments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`createExperiment failed: ${res.status} ${await res.text()}`);
  return res.json();
}

export async function listExperiments(): Promise<ExperimentListItem[]> {
  const res = await fetch(`${API_BASE}/api/experiments`, { cache: "no-store" });
  if (!res.ok) throw new Error("listExperiments failed");
  return res.json();
}

export async function getExperiment(id: string): Promise<Experiment> {
  const res = await fetch(`${API_BASE}/api/experiments/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`getExperiment failed: ${res.status}`);
  return res.json();
}

export async function branchExperiment(id: string, overrides: Partial<ExperimentCreateBody>): Promise<Experiment> {
  const res = await fetch(`${API_BASE}/api/experiments/${id}/branch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(overrides),
  });
  if (!res.ok) throw new Error(`branchExperiment failed: ${res.status} ${await res.text()}`);
  return res.json();
}

export async function annotateExperiment(id: string, annotation: string): Promise<Experiment> {
  const res = await fetch(`${API_BASE}/api/experiments/${id}/annotation`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ annotation }),
  });
  if (!res.ok) throw new Error("annotateExperiment failed");
  return res.json();
}

export async function deleteExperiment(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/experiments/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("deleteExperiment failed");
}

// ── Experiment Health ─────────────────────────────────────────────────────

export interface ExperimentHealth {
  assumptions: { label: string; detail: string }[];
  uncertainty: { n_mc: number; quantified: boolean; note: string };
  validation: { status: string; detail: string; scores: Record<string, number | boolean> | null };
  limitations: string[];
  model_fingerprint: string;
}

export async function fetchExperimentHealth(id: string): Promise<ExperimentHealth> {
  const res = await fetch(`${API_BASE}/api/experiments/${id}/health`, { cache: "no-store" });
  if (!res.ok) throw new Error("fetchExperimentHealth failed");
  return res.json();
}

// ── Scientific Notebook ────────────────────────────────────────────────────

export interface NotebookListItem {
  id: string;
  title: string;
  description: string | null;
  author: string | null;
  created_at: string;
  updated_at: string;
}

export interface NotebookEntry {
  id: string;
  entry_type: "experiment" | "comparison" | "note";
  text: string | null;
  created_at: string;
  experiments: {
    id: string;
    label: string;
    mode: string;
    anchor_year: number;
    target_year: number;
    summary: Record<string, number | string>;
    baseline_summary: Record<string, number | string>;
    cascade_total_affected: number;
    explanation: string | null;
    health: ExperimentHealth;
  }[];
}

export interface Notebook {
  metadata: NotebookListItem;
  entries: NotebookEntry[];
}

export async function createNotebook(title: string, description?: string, author?: string): Promise<NotebookListItem> {
  const res = await fetch(`${API_BASE}/api/notebooks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, description, author }),
  });
  if (!res.ok) throw new Error("createNotebook failed");
  return res.json();
}

export async function listNotebooks(): Promise<NotebookListItem[]> {
  const res = await fetch(`${API_BASE}/api/notebooks`, { cache: "no-store" });
  if (!res.ok) throw new Error("listNotebooks failed");
  return res.json();
}

export async function getNotebook(id: string): Promise<Notebook> {
  const res = await fetch(`${API_BASE}/api/notebooks/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error("getNotebook failed");
  return res.json();
}

export async function addNotebookEntry(
  notebookId: string,
  entryType: "experiment" | "comparison" | "note",
  experimentIds: string[],
  text?: string
): Promise<NotebookEntry> {
  const res = await fetch(`${API_BASE}/api/notebooks/${notebookId}/entries`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ entry_type: entryType, experiment_ids: experimentIds, text }),
  });
  if (!res.ok) throw new Error("addNotebookEntry failed");
  return res.json();
}

export async function deleteNotebook(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/notebooks/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("deleteNotebook failed");
}

export function notebookExportUrl(id: string, format: "markdown" | "json" = "markdown"): string {
  return `${API_BASE}/api/notebooks/${id}/export?format=${format}`;
}
