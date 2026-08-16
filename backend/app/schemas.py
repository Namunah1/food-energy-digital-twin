from typing import Optional, Literal
from pydantic import BaseModel, Field


class ShockInput(BaseModel):
    shock_type: Literal[
        "climate_drought", "energy_crisis", "pandemic", "financial_crisis",
        "export_ban", "war", "fertilizer_shortage", "shipping_disruption",
        "currency_collapse",
    ]
    start_step: int = Field(5, ge=0, le=60)
    duration: int = Field(1, ge=1, le=15)
    severity: float = Field(50, ge=0, le=100)
    scope: float = Field(30, ge=0, le=100)
    target_node: Optional[str] = None


class ResponseLever(BaseModel):
    reserve_mandate: bool = False
    trade_diversification: bool = False
    trader_regulation: bool = False


class SimulationRequest(BaseModel):
    shocks: list[ShockInput] = []
    responses: list[str] = []   # subset of {"reserve_mandate","trade_diversification","trader_regulation"}
    n_steps: int = Field(30, ge=1, le=60)
    seed: int = 42
    compare_baseline: bool = True
    capture_snapshots: bool = False  # per-step node snapshots for Timeline Replay


class ResearchScenarioRequest(BaseModel):
    name: str
    n_mc: int = Field(5, ge=1, le=20)
    n_steps: int = Field(30, ge=1, le=60)
    seed: int = 42


class ComparisonRun(BaseModel):
    kind: Literal["research", "custom"]
    name: Optional[str] = None            # required if kind == "research"
    id: Optional[str] = None              # required if kind == "custom"
    label: Optional[str] = None
    shocks: list[ShockInput] = []
    responses: list[str] = []


class ComparisonRequest(BaseModel):
    runs: list[ComparisonRun] = Field(..., min_length=1, max_length=4)
    n_steps: int = Field(25, ge=5, le=40)
    seed: int = 42


class AdvisorRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)


class ProjectionRequest(BaseModel):
    shocks: list[ShockInput] = []
    responses: list[str] = []
    target_year: int = Field(..., ge=2001, le=2060)
    start_year: Optional[int] = Field(None, ge=2000, le=2024)
    n_mc: int = Field(8, ge=3, le=20)
    seed: int = 42
    explain: bool = True


class CascadeTraceRequest(BaseModel):
    shocks: list[ShockInput] = []
    responses: list[str] = []
    start_year: int = Field(2022, ge=2000, le=2024)
    n_steps: int = Field(8, ge=2, le=20)
    seed: int = 42


class PolicyOptimizationRequest(BaseModel):
    shocks: list[ShockInput] = []
    start_year: int = Field(2022, ge=2000, le=2024)
    n_steps: int = Field(15, ge=5, le=30)
    seed: int = 42


class CustomLeverSpec(BaseModel):
    """
    PHASE B (this session): one node-targeted policy lever request.
    `type` must be one of scenarios.CUSTOM_LEVER_BUILDERS' keys:
    food_aid, coordinated_export_restriction, climate_adaptation,
    import_tariff, energy_intervention, fertilizer_support_interim,
    global_reserve_pool. Remaining fields are lever-specific (e.g.
    food_aid needs donor/recipient/aid_fraction) — validated at the
    scientific-model layer (scenarios.build_custom_lever), not here,
    since the field set genuinely differs per lever type and Pydantic's
    strict per-model validation would otherwise require seven near-
    duplicate request models for what is, at the model layer, one dict.
    """
    type: str
    node: Optional[str] = None
    donor: Optional[str] = None
    recipient: Optional[str] = None
    target_nodes: Optional[list[str]] = None
    aid_fraction: Optional[float] = None
    export_fraction_cap: Optional[float] = None
    effectiveness: Optional[float] = None
    tariff_multiplier: Optional[float] = None
    release_fraction: Optional[float] = None
    mode: Optional[str] = None
    support_level: Optional[float] = None
    levy_threshold_margin: Optional[float] = None
    levy_rate: Optional[float] = None


class PolicySearchRequest(BaseModel):
    """
    PHASE A/B/D (this session): request schema for the combinatorial +
    intensity + node-level policy search (scenarios.policy_search()),
    distinct from PolicyOptimizationRequest above (which remains unchanged
    and drives the original fixed-5-lever /api/policy_optimization
    endpoint).
    """
    shocks: list[ShockInput] = []
    start_year: int = Field(2022, ge=2000, le=2024)
    n_steps: int = Field(15, ge=5, le=30)
    n_random: int = Field(40, ge=0, le=200,
        description="Number of randomly-sampled lever combinations to "
                     "evaluate in addition to the 5 fixed single-lever "
                     "baselines. Runtime scales linearly (~1s/candidate).")
    include_fixed_levers: bool = True
    custom_levers: list[CustomLeverSpec] = Field(default_factory=list,
        description="PHASE B: node-targeted levers (food aid, tariffs, "
                     "adaptation funding, etc.) — see CustomLeverSpec.")
    include_node_targeted_sampling: bool = Field(False,
        description="PHASE D: additionally let the search choose WHICH "
                     "node(s) to target for food aid/adaptation/tariff "
                     "levers, rather than requiring an explicit node in "
                     "custom_levers.")
    node_pool: Optional[list[str]] = Field(None,
        description="PHASE D: restrict node-targeted sampling to this "
                     "subset of countries. Defaults to all 35 if omitted.")
    max_budget: Optional[float] = Field(None,
        description="PHASE D: illustrative cost budget (arbitrary units, "
                     "NOT real currency — see LEVER_COSTS_ILLUSTRATIVE). "
                     "Over-budget candidates are annotated, not dropped.")
    seed: int = 42


class NodeLevelSearchRequest(BaseModel):
    """
    PHASE D (this session): focused search over WHICH node(s) a single
    lever type should target — answers "which N countries should receive
    [lever] to minimise global PAR" directly.
    """
    lever_type: str = Field(..., description="One of: food_aid, "
        "climate_adaptation, import_tariff, coordinated_export_restriction")
    node_pool: list[str] = Field(..., min_length=2,
        description="Candidate nodes to search over (e.g. all 35, or a "
                     "caller-restricted subset).")
    shocks: list[ShockInput] = []
    start_year: int = Field(2022, ge=2000, le=2024)
    n_steps: int = Field(15, ge=5, le=30)
    n_random: int = Field(30, ge=1, le=200)
    max_budget: Optional[float] = None
    seed: int = 42


# ── Experiment Studio (canonical entry point) ────────────────────────────────

class ExperimentCreateRequest(BaseModel):
    label: Optional[str] = None
    mode: Literal["historical", "counterfactual", "projection"]
    anchor_year: int = Field(2022, ge=2000, le=2024)
    target_year: int = Field(2030, ge=2001, le=2060)
    known_episode: Optional[str] = None  # "2008" | "2011" | "2020" | "2022" | "2004_niger"
    shocks: list[ShockInput] = []
    responses: list[str] = []
    n_mc: int = Field(1, ge=1, le=20)
    seed: int = 42
    explain: bool = True
    evaluate_policies: bool = False
    target_country: Optional[str] = None
    parent_id: Optional[str] = None
    annotation: Optional[str] = None


class ExperimentBranchRequest(BaseModel):
    label: Optional[str] = None
    mode: Optional[Literal["historical", "counterfactual", "projection"]] = None
    anchor_year: Optional[int] = Field(None, ge=2000, le=2024)
    target_year: Optional[int] = Field(None, ge=2001, le=2060)
    known_episode: Optional[str] = None
    shocks: Optional[list[ShockInput]] = None
    responses: Optional[list[str]] = None
    n_mc: Optional[int] = Field(None, ge=1, le=20)
    seed: Optional[int] = None
    evaluate_policies: Optional[bool] = None
    annotation: Optional[str] = None


class AnnotationRequest(BaseModel):
    annotation: str = Field(..., max_length=2000)


# ── Scientific Notebook ────────────────────────────────────────────────────

class NotebookCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    author: Optional[str] = Field(None, max_length=200)


class NotebookEntryCreateRequest(BaseModel):
    entry_type: Literal["experiment", "comparison", "note"]
    experiment_ids: list[str] = []
    text: Optional[str] = Field(None, max_length=5000)


class NotebookEntryUpdateRequest(BaseModel):
    text: str = Field(..., max_length=5000)
