"""
trade.py
--------
Trade network construction and flow resolution.

Framework : Gambhir et al. (2025) + Homer-Dixon et al. (2015)
Phase     : 2 — Real full-mesh network from network_weights.csv

Implements (per EQUATIONS.md §7):
  - Full mesh (35×35 directed) loaded from data/processed/network_weights.csv
  - Gravity trade volumes with real C_ij (capacity), κ_ij (cost), ρ_ij (political risk)
  - 3-regime export fraction from agent.export_fraction (§11)
  - Affordability constraint: affordable_kcal = (K_i / p^1.2) × 10^12
  - Export-ban contagion (RC mechanism, §11)

Phase 3 hook: energy_cost_push added to price update (done in prices.py)
Phase 5 hook: trader_agents can intercept flows (placeholder in execute_trade_step)
"""

import numpy as np
import pandas as pd
import networkx as nx
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from model import FoodModel

# ── Gravity constants ─────────────────────────────────────────────────────────
G_BASE = 6e10        # calibrated gravity constant (kcal/year)
PRICE_ELASTICITY = 1.2

# ── Export ban contagion ──────────────────────────────────────────────────────
BAN_CONTAGION_RATE = 0.30   # base probability modifier
BAN_CONTAGION_CAP  = 0.80

# ── Minimum trade volume to bother processing ─────────────────────────────────
MIN_TRADE_VOLUME = 1e6   # kcal (below this, skip the edge)


def build_trade_network(data_dir: Path) -> nx.DiGraph:
    """
    Load the real 35-node full-mesh directed trade network from
    data/processed/network_weights.csv (produced by Phase 1 data_pipeline.py).

    Each directed edge (i → j) carries:
      C_ij_capacity  : max trade capacity (kcal/year proxy)
      kappa_ij_cost  : transaction cost [0,1]
      rho_ij_risk    : political risk [0,1]
      active         : bool (can be set False by STC engine / shocks)

    Returns
    -------
    G : nx.DiGraph with node attributes {name} and edge attributes above
    """
    csv_path = data_dir / "processed" / "network_weights.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"network_weights.csv not found at {csv_path}\n"
            f"Run src/data_pipeline.py first to generate Phase 1 data."
        )

    df = pd.read_csv(csv_path)

    G = nx.DiGraph()

    # Add all nodes first (populated later by model._create_agents)
    nodes = sorted(set(df["from_node"]) | set(df["to_node"]))
    for n in nodes:
        G.add_node(n, name=n)

    # Add directed edges (network_weights.csv has one row per ordered pair)
    required_cols = {"from_node", "to_node", "C_ij_capacity", "kappa_ij_cost", "rho_ij_risk"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"network_weights.csv missing columns: {missing}")

    for _, row in df.iterrows():
        src = row["from_node"]
        dst = row["to_node"]
        if src == dst:
            continue

        cap_raw  = float(row["C_ij_capacity"])
        # Use ATM-corrected capacity if available (see network_weights.csv C_ij_corrected).
        # C_ij_corrected = C_ij_capacity × sqrt(ATM_from × ATM_to) where ATM is the
        # Agricultural Trade Multiplier derived from USDA PSD 2022 export volumes vs
        # the gravity model's implied capacity shares. This partially corrects the
        # gravity model's systematic underweighting of agricultural exporters (Argentina,
        # Australia, Ukraine, Brazil) relative to large-GDP industrial economies
        # (Germany, UK, France). Full correction requires the FAO Detailed Trade Matrix
        # (currently blocked; see data/raw/fao/README.md for manual download instructions).
        cap  = float(row.get("C_ij_corrected", cap_raw))
        kap  = float(row["kappa_ij_cost"])
        risk = float(row["rho_ij_risk"])

        # Clamp risk to [0.05, 0.95]
        risk = float(np.clip(risk, 0.05, 0.95))

        G.add_edge(
            src, dst,
            C_ij      = cap,
            kappa_ij  = kap,
            rho_ij    = risk,
            active    = True,
        )

    return G


def _effective_risk(G: nx.DiGraph, src: str, dst: str,
                    sanction_penalty: float = 0.0) -> float:
    """
    ρ_ij_eff = rho_ij + sanction_penalty   clamped [0.05, 0.95]
    """
    base = G[src][dst]["rho_ij"]
    return float(np.clip(base + sanction_penalty, 0.05, 0.95))


def _gravity_volume(
    seller,
    buyer,
    edge_cap: float,
    kappa: float,
    global_price: float,
) -> float:
    """
    Trade volume for directed edge (seller → buyer).

    Constraints applied in order:
      1. Seller's export-available stock:
             avail = export_fraction × food_imperish
      2. Edge capacity (C_ij from real data), discounted by kappa and logistics
      3. Buyer deficit (demand − current stock, capped at 1.2×)
      4. Buyer affordability: K_buyer / (p × tariff_mult)^1.2 × 10^12

    PHASE B (this session): `tariff_mult` is an optional per-buyer import
    tariff/subsidy multiplier on the effective price used for the
    affordability constraint only, read via getattr with default 1.0 so
    this is BYTE-IDENTICAL to the original formula for every agent
    without the attribute set. >1.0 = tariff (reduces affordability);
    <1.0 = subsidy (increases affordability). Set only by
    make_import_tariff_lever() in scenarios.py.
    """
    # Seller supply available for export
    export_avail = seller.export_fraction * seller.food_imperish

    # Cap by edge capacity (cost-discounted, logistics-reduced)
    logistics_factor = 1.0 - max(
        seller.logistics_disruption,
        buyer.logistics_disruption,
    )
    cap_volume = edge_cap * (1.0 - kappa) * logistics_factor

    # Buyer deficit (only import what is needed)
    D_buyer = buyer.caloric_demand()
    current_supply = buyer.food_imperish + buyer.food_perish + buyer.food_animal
    buyer_deficit = max(0.0, D_buyer - current_supply)

    # Affordability (tariff/subsidy-adjusted effective price)
    tariff_mult = getattr(buyer, "import_tariff_multiplier", 1.0)
    effective_price = global_price * tariff_mult
    if effective_price > 0:
        affordable_kcal = (buyer.capital / (effective_price ** PRICE_ELASTICITY)) * 1e12
    else:
        affordable_kcal = float("inf")

    volume = min(export_avail, cap_volume, buyer_deficit * 1.2, affordable_kcal)
    return max(0.0, volume)


def execute_trade_step(model: "FoodModel"):
    """
    For each active directed edge (seller → buyer) in the trade network:
      1. Skip if edge deactivated or seller has export ban (fraction == 0)
      2. Apply political risk gate (Bernoulli trial)
      3. Compute gravity-model trade volume
      4. Transfer food stocks and update capital accumulators
      5. Export-ban contagion (RC mechanism)

    Phase 5 hook: trader interception stub (see _trader_intercept)
    """
    G   = model.network
    rng = model.rng
    p   = model.price_system.price
    sanction_penalty = getattr(model, "sanction_penalty", 0.0)

    for src, dst, edge_data in list(G.edges(data=True)):
        if not edge_data.get("active", True):
            continue

        seller = model.agent_map.get(src)
        buyer  = model.agent_map.get(dst)
        if seller is None or buyer is None:
            continue

        # ── Seller export policy ──────────────────────────────────────────────
        if seller.export_fraction <= 0.0:
            _propagate_export_ban(model, src)
            continue

        # ── Political risk gate ───────────────────────────────────────────────
        rho_eff = _effective_risk(G, src, dst, sanction_penalty)
        if rng.random() < rho_eff:
            continue

        # ── Gravity trade volume ──────────────────────────────────────────────
        volume = _gravity_volume(
            seller, buyer,
            edge_data["C_ij"],
            edge_data["kappa_ij"],
            p,
        )

        if volume < MIN_TRADE_VOLUME:
            continue

        # ── Phase 5 hook: trader interception (no-op until Phase 5) ──────────
        volume = _trader_intercept(model, src, dst, volume)

        if volume < MIN_TRADE_VOLUME:
            continue

        # ── Transfer ──────────────────────────────────────────────────────────
        volume = min(volume, seller.food_imperish * 0.95)  # safety clamp
        if volume <= 0:
            continue

        seller.food_imperish -= volume
        buyer.food_imperish  += volume

        # Capital flows
        trade_value = volume * p * 1e-12   # USD bn proxy
        seller.exports_this_step    += volume
        buyer.imports_this_step     += volume
        seller.trade_value_exported += trade_value
        buyer.trade_value_imported  += trade_value

        # GDP nudge (trade adds/removes from GDP proxy)
        seller.gdp = max(0.1, seller.gdp + 0.001 * trade_value)
        buyer.gdp  = max(0.1, buyer.gdp  - 0.001 * trade_value)


def _propagate_export_ban(model: "FoodModel", banning_node: str):
    """
    RC export-ban contagion: neighbours of a banning country may panic-ban.

    P(j bans | i bans) = BAN_CONTAGION_RATE × max(0, 1 − σⱼ)  ≤ 0.80
    """
    G   = model.network
    rng = model.rng

    for _, dst in G.out_edges(banning_node):
        neighbour = model.agent_map.get(dst)
        if neighbour is None or neighbour.export_ban:
            continue

        contagion_prob = np.clip(
            BAN_CONTAGION_RATE * max(0.0, 1.0 - neighbour.food_security),
            0.0,
            BAN_CONTAGION_CAP,
        )
        if rng.random() < contagion_prob:
            neighbour.export_ban      = True
            neighbour.export_fraction = 0.0


def _trader_intercept(model: "FoodModel", src: str, dst: str, volume: float) -> float:
    """
    Phase 5 hook: trader agents can intercept and reduce trade flows.
    Returns the volume after any trader extraction.
    No-op in Phase 2; overridden by political_economy.py in Phase 5.
    """
    trader_module = getattr(model, "trader_module", None)
    if trader_module is not None:
        return trader_module.intercept(src, dst, volume)
    return volume


def compute_network_density(model: "FoodModel") -> float:
    """
    SAV_connect(t) = active_edges / max_possible_edges   (§13)
    Used by metrics.py for Gambhir SAV indices.
    """
    G = model.network
    active = sum(1 for _, _, d in G.edges(data=True) if d.get("active", True))
    max_edges = G.number_of_nodes() * (G.number_of_nodes() - 1)
    return active / max(max_edges, 1)


def compute_trade_herfindahl(model: "FoodModel") -> float:
    """
    SAV_power(t) = HHI of trade flow by node (§13)
    Measures concentration of trade power.
    """
    flows = {
        name: agent.exports_this_step
        for name, agent in model.agent_map.items()
    }
    total = sum(flows.values())
    if total <= 0:
        return 0.0
    shares = [v / total for v in flows.values()]
    return sum(s ** 2 for s in shares)
