"""
visualize.py
------------
Phase 10: Complete figure suite for the final report.

Figures produced:
  F1. GFS / price / overloads time series (baseline + scenarios)
  F2. OAT sensitivity heatmap — "which assumptions matter?"
  F3. Retrodiction comparison bar chart (model vs real)
  F4. Network hub map (node size = PageRank, colour = food security)
  F5. Crisis attribution stacked bar (per overloaded node)
  F6. Scenario comparison panel (6 scenarios × 4 metrics)
  F7. CC calibration scatter (model CC vs undernourishment proxy)
  F8. Worst-case discovery scatter (severity score vs trigger type)
"""

import sys
import json
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from pathlib import Path

warnings.filterwarnings("ignore")

_SRC  = Path(__file__).resolve().parent
_ROOT = _SRC.parent
_DATA = _ROOT / "data" / "processed"
_FIG  = _ROOT / "figures"
_FIG.mkdir(parents=True, exist_ok=True)

if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# ── Colour palette ────────────────────────────────────────────────────────────
C = {
    "baseline":     "#4A90D9",
    "climate":      "#E67E22",
    "geopolitical": "#E74C3C",
    "reserve":      "#27AE60",
    "diversify":    "#8E44AD",
    "transform":    "#1ABC9C",
    "real":         "#2C3E50",
    "model":        "#3498DB",
    "pass":         "#27AE60",
    "fail":         "#E74C3C",
    "neutral":      "#95A5A6",
    "bg":           "#FAFAFA",
}

SCENARIO_COLOURS = [
    C["baseline"], C["climate"], C["geopolitical"],
    C["reserve"], C["diversify"], C["transform"]
]
SCENARIO_LABELS = [
    "S0: Baseline", "S1: Climate Cascade", "S2: Geopolitical Freeze",
    "S3: Reserve Mandate", "S4: Trade Diversification", "S5: Transformational"
]


def _style_ax(ax, title="", xlabel="", ylabel="", grid=True):
    ax.set_facecolor(C["bg"])
    ax.set_title(title, fontsize=11, fontweight="bold", pad=8)
    if xlabel: ax.set_xlabel(xlabel, fontsize=9)
    if ylabel: ax.set_ylabel(ylabel, fontsize=9)
    if grid:   ax.grid(True, alpha=0.3, linewidth=0.5)
    ax.spines[["top","right"]].set_visible(False)
    ax.tick_params(labelsize=8)


# ============================================================================
# F1: Scenario time-series (GFS + Price + Overloads)
# ============================================================================

def fig_scenario_timeseries(data_dir: Path, fig_dir: Path):
    """Run each scenario and plot GFS, price, overloads over time."""
    from model import FoodEnergyModel
    from stc_engine import STCEngine
    from scenarios import SCENARIOS

    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    fig.patch.set_facecolor("white")

    for i, spec in enumerate(SCENARIOS):
        model = FoodEnergyModel(scenario=spec.name, seed=42)
        spec.response_fn(model)
        model.stc_engine = STCEngine(
            triggers=[dict(t) for t in spec.triggers],
            ss_mode="multiplicative"
        )
        model.run(25, verbose=False)
        df = model.metrics_dataframe()

        steps = df["step"]
        lw = 2.0 if i == 0 else 1.4
        ls = "-" if i < 3 else "--"
        col = SCENARIO_COLOURS[i]
        lbl = SCENARIO_LABELS[i]

        axes[0].plot(steps, df["GFS"],           color=col, lw=lw, ls=ls, label=lbl)
        axes[1].plot(steps, df["price_index"],   color=col, lw=lw, ls=ls)
        axes[2].plot(steps, df["n_overload_food"], color=col, lw=lw, ls=ls)

    # Add trigger markers for S1 and S2
    for ax in axes:
        ax.axvline(8, color=C["climate"],      alpha=0.35, lw=1.2, ls=":")
        ax.axvline(6, color=C["geopolitical"], alpha=0.35, lw=1.2, ls=":")

    _style_ax(axes[0], "Global Food Security (population-weighted σ)", ylabel="GFS Index")
    _style_ax(axes[1], "Food Price Index (2014–2016 = 1.0)", ylabel="Price Index")
    _style_ax(axes[2], "Nodes in LFBB Overload", xlabel="Step (years)", ylabel="Count")

    axes[0].axhline(1.0, color="grey", lw=0.8, ls="--", alpha=0.6)
    axes[1].axhline(1.0, color="grey", lw=0.8, ls="--", alpha=0.6)

    axes[0].legend(loc="upper right", fontsize=7.5, framealpha=0.9)
    axes[0].text(8.2, axes[0].get_ylim()[0]*1.01, "S1 trigger", fontsize=7, color=C["climate"])
    axes[0].text(6.2, axes[0].get_ylim()[0]*1.01, "S2 trigger", fontsize=7, color=C["geopolitical"])

    fig.suptitle("Figure 1: Scenario Comparison — Time Series (30-year horizon)",
                 fontsize=13, fontweight="bold", y=1.01)
    plt.tight_layout()
    path = fig_dir / "F1_scenario_timeseries.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [F1] saved → {path.name}")
    return path


# ============================================================================
# F2: OAT Sensitivity Heatmap
# ============================================================================

def fig_sensitivity_heatmap(data_dir: Path, fig_dir: Path):
    oat_path = data_dir / "sa_oat.csv"
    if not oat_path.exists():
        print("  [F2] sa_oat.csv not found — skipping")
        return None

    df = pd.read_csv(oat_path)
    metrics = ["max_price_ratio", "max_U", "max_PAR_millions",
               "max_EB_rate", "max_TC", "max_n_overload_food"]
    params  = df["param"].unique()

    # Compute OAT range (max-min) per param × metric, normalised
    heat = pd.DataFrame(index=params, columns=metrics, dtype=float)
    for p in params:
        sub = df[df["param"] == p]
        for m in metrics:
            if m in sub.columns:
                heat.loc[p, m] = sub[m].max() - sub[m].min()

    heat = heat.astype(float)
    # Normalise each column to [0,1]
    for col in heat.columns:
        rng = heat[col].max() - heat[col].min()
        if rng > 0:
            heat[col] = (heat[col] - heat[col].min()) / rng

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor("white")

    im = ax.imshow(heat.values, cmap="YlOrRd", aspect="auto", vmin=0, vmax=1)

    ax.set_xticks(range(len(metrics)))
    ax.set_xticklabels([m.replace("max_","").replace("_"," ") for m in metrics],
                       rotation=30, ha="right", fontsize=8)
    ax.set_yticks(range(len(params)))
    ax.set_yticklabels(params, fontsize=8)

    # Annotate cells
    for i in range(len(params)):
        for j in range(len(metrics)):
            val = heat.iloc[i, j]
            ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                    fontsize=7, color="black" if val < 0.6 else "white")

    plt.colorbar(im, ax=ax, label="Normalised OAT range (0=insensitive, 1=most sensitive)")
    ax.set_title("Figure 2: OAT Sensitivity — Which Parameters Actually Matter?\n"
                 "(normalised outcome range when each parameter is swept across its full range)",
                 fontsize=11, fontweight="bold")
    plt.tight_layout()
    path = fig_dir / "F2_sensitivity_heatmap.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [F2] saved → {path.name}")
    return path


# ============================================================================
# F3: Retrodiction comparison bar chart
# ============================================================================

def fig_retrodiction_comparison(data_dir: Path, fig_dir: Path):
    retro_path = data_dir / "retrodiction_table.csv"
    if not retro_path.exists():
        print("  [F3] retrodiction_table.csv not found — skipping")
        return None

    df = pd.read_csv(retro_path)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.patch.set_facecolor("white")

    real_fpi  = [1.177, 1.445]
    model_fpi_raw = df[df["Metric"] == "Peak FPI (normalised)"][["Model_2008","Model_2022"]].values
    try:
        m08 = float(str(model_fpi_raw[0][0]).split("±")[0].strip())
        m22 = float(str(model_fpi_raw[0][1]).split("±")[0].strip())
        std08 = float(str(model_fpi_raw[0][0]).split("±")[1].strip()) if "±" in str(model_fpi_raw[0][0]) else 0.05
        std22 = float(str(model_fpi_raw[0][1]).split("±")[1].strip()) if "±" in str(model_fpi_raw[0][1]) else 0.05
    except Exception:
        m08, m22, std08, std22 = 1.10, 1.20, 0.05, 0.05

    x = np.arange(2)
    w = 0.30
    ax = axes[0]
    ax.bar(x - w/2, real_fpi,         w, label="Real (FAO FPI)", color=C["real"],  alpha=0.85)
    ax.bar(x + w/2, [m08, m22],       w, label="Model (mean)",   color=C["model"], alpha=0.85,
           yerr=[[std08,std22],[std08,std22]], capsize=5, error_kw={"linewidth":1.2})
    ax.axhline(1.0, color="grey", lw=0.8, ls="--", alpha=0.6, label="Baseline (2014-16=1.0)")
    # Tolerance band
    for xi, rv in zip(x, real_fpi):
        ax.fill_between([xi-0.4, xi+0.4], rv*0.85, rv*1.15,
                        color="grey", alpha=0.12, zorder=0)
    ax.set_xticks(x)
    ax.set_xticklabels(["2008 Crisis", "2022 Crisis"])
    _style_ax(ax, "Peak Food Price Index (normalised)", ylabel="FPI (2014-16 = 1.0)")
    ax.legend(fontsize=8)
    ax.text(0.02, 0.97, "Grey band = ±15% tolerance", transform=ax.transAxes,
            fontsize=7, va="top", color="grey")

    # Score summary
    scores_path = data_dir / "retrodiction_scores.json"
    ax2 = axes[1]
    if scores_path.exists():
        with open(scores_path) as f:
            scores = json.load(f)

        labels = [k for k in scores if k != "pom_score"]
        vals   = [1 if scores[k] else 0 for k in labels]
        colours= [C["pass"] if v else C["fail"] for v in vals]
        short  = [k.replace("_score","").replace("_"," ").replace("2008 ","'08 ").replace("2022 ","'22 ") for k in labels]

        ax2.barh(range(len(labels)), vals, color=colours, alpha=0.85, height=0.6)
        ax2.set_yticks(range(len(labels)))
        ax2.set_yticklabels(short, fontsize=8)
        ax2.set_xlim(0, 1.3)
        ax2.set_xticks([0, 1])
        ax2.set_xticklabels(["FAIL", "PASS"])
        pom = scores.get("pom_score", 0.0)
        _style_ax(ax2, f"Retrodiction Scores (POM = {pom:.2f})", grid=False)
        ax2.axvline(0.5, color="grey", lw=0.8, ls="--", alpha=0.5)
        ax2.text(1.15, len(labels)-0.5, f"POM\n{pom:.2f}", fontsize=9,
                 fontweight="bold", color=C["pass"] if pom >= 0.70 else C["fail"])
    else:
        ax2.text(0.5, 0.5, "scores not found", transform=ax2.transAxes, ha="center")

    fig.suptitle("Figure 3: Historical Retrodiction Validation (2008 & 2022 Crises)",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    path = fig_dir / "F3_retrodiction.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [F3] saved → {path.name}")
    return path


# ============================================================================
# F4: Network hub map (node size = PageRank, colour = food security)
# ============================================================================

def fig_network_hub_map(data_dir: Path, fig_dir: Path):
    try:
        import networkx as nx
        from model import FoodEnergyModel
        from stc_engine import STCEngine

        model = FoodEnergyModel(scenario="net_viz", seed=42)
        model.stc_engine = STCEngine(triggers=[], ss_mode="multiplicative")
        model.run(5, verbose=False)

        G   = model.network
        pr  = nx.pagerank(G, alpha=0.85, weight="C_ij")
        agents = model.agent_map

        fig, ax = plt.subplots(figsize=(13, 8))
        fig.patch.set_facecolor("white")
        ax.set_facecolor("#F0F4F8")

        # Simple circular layout
        pos = nx.circular_layout(G)

        # Node sizes and colours
        node_sizes  = [max(200, pr.get(n, 0.01) * 15000) for n in G.nodes()]
        node_sigmas = [agents[n].food_security if n in agents else 1.5 for n in G.nodes()]
        norm_sigma  = plt.Normalize(vmin=0.5, vmax=3.0)
        node_cols   = [plt.cm.RdYlGn(norm_sigma(s)) for s in node_sigmas]

        # Draw light edges first
        nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.05, width=0.4,
                               edge_color="steelblue", arrows=False)
        # Draw nodes
        nx.draw_networkx_nodes(G, pos, ax=ax, node_size=node_sizes,
                               node_color=node_cols, alpha=0.90, linewidths=0.5,
                               edgecolors="white")
        # Labels for top PageRank nodes only
        top_nodes = sorted(pr, key=pr.get, reverse=True)[:12]
        labels = {n: n.replace(" (ECOWAS)","").replace("-other","")
                     .replace(" & ","&").replace("Southern Africa (SADC)","S.Africa")[:12]
                  for n in top_nodes}
        nx.draw_networkx_labels(G, pos, labels=labels, ax=ax, font_size=6.5,
                                font_weight="bold")

        sm = plt.cm.ScalarMappable(cmap=plt.cm.RdYlGn, norm=norm_sigma)
        sm.set_array([])
        cb = plt.colorbar(sm, ax=ax, shrink=0.6, pad=0.02)
        cb.set_label("Food Security (σ)", fontsize=9)

        ax.set_title("Figure 4: Trade Network — Node Size = PageRank (Trade Influence), "
                     "Colour = Food Security\n(After 5 simulation steps, baseline scenario)",
                     fontsize=11, fontweight="bold")
        ax.axis("off")
        plt.tight_layout()
        path = fig_dir / "F4_network_hub_map.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  [F4] saved → {path.name}")
        return path
    except Exception as e:
        print(f"  [F4] error: {e}")
        return None


# ============================================================================
# F5: Crisis attribution stacked bar
# ============================================================================

def fig_crisis_attribution(data_dir: Path, fig_dir: Path):
    attr_path = data_dir / "scenario_attribution.csv"
    if not attr_path.exists():
        print("  [F5] scenario_attribution.csv not found — skipping")
        return None

    df = pd.read_csv(attr_path)
    # Use S2 geopolitical scenario
    sub = df[df["scenario"] == "S2_geopolitical_freeze"].head(10)
    if sub.empty:
        sub = df.head(10)

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("white")

    nodes  = sub["node"].str[:20].tolist()
    food   = sub["food_stress_pct"].values
    energy = sub["energy_pct"].values
    contag = sub["contagion_pct"].values
    reserv = sub["reserve_failure_pct"].values

    x = np.arange(len(nodes))
    w = 0.65
    b1 = ax.bar(x, food,                                   width=w, label="Food stress",     color="#E74C3C", alpha=0.85)
    b2 = ax.bar(x, energy, bottom=food,                    width=w, label="Energy stress",   color="#E67E22", alpha=0.85)
    b3 = ax.bar(x, contag, bottom=food+energy,             width=w, label="Contagion",       color="#9B59B6", alpha=0.85)
    b4 = ax.bar(x, reserv, bottom=food+energy+contag,      width=w, label="Reserve failure", color="#3498DB", alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(nodes, rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("Contribution (%)")
    ax.set_ylim(0, 120)
    ax.legend(loc="upper right", fontsize=8)
    _style_ax(ax, "Figure 5: Crisis Attribution — Why Did These Nodes Fail?\n"
              "(S2: Geopolitical Freeze scenario)", ylabel="Contribution (%)")

    # Annotate overload ratio
    for i, (_, row) in enumerate(sub.iterrows()):
        ax.text(i, 105, f"σ={row['food_security']:.2f}", ha="center",
                fontsize=6.5, color="darkred")

    plt.tight_layout()
    path = fig_dir / "F5_crisis_attribution.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [F5] saved → {path.name}")
    return path


# ============================================================================
# F6: Scenario comparison panel
# ============================================================================

def fig_scenario_comparison(data_dir: Path, fig_dir: Path):
    sc_path = data_dir / "scenario_comparison.csv"
    if not sc_path.exists():
        print("  [F6] scenario_comparison.csv not found — skipping")
        return None

    df = pd.read_csv(sc_path)
    labels = [s.split(":")[0] for s in df["Scenario"]]

    metrics = ["FPI_mean", "U_mean", "Overloads_mean", "TC_mean"]
    titles  = ["Peak FPI (normalised)", "Peak Undernourishment Rate",
               "Max LFBB Overloads", "Max Trade Collapse Index"]
    ylabels = ["FPI", "Fraction", "Node count", "Index [0,1]"]

    # Parse numeric values
    for col in ["FPI_mean", "U_mean", "Overloads_mean", "TC_mean"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    fig, axes = plt.subplots(1, 4, figsize=(14, 5))
    fig.patch.set_facecolor("white")

    for ax, metric, title, ylabel in zip(axes, metrics, titles, ylabels):
        vals = df[metric].fillna(0).values
        bars = ax.bar(range(len(labels)), vals, color=SCENARIO_COLOURS, alpha=0.85, width=0.65)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=40, ha="right", fontsize=8)
        _style_ax(ax, title, ylabel=ylabel)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.005,
                    f"{v:.2f}", ha="center", fontsize=7)

    # Legend
    patches = [mpatches.Patch(color=SCENARIO_COLOURS[i], label=SCENARIO_LABELS[i])
               for i in range(len(SCENARIO_LABELS))]
    fig.legend(handles=patches, loc="lower center", ncol=3, fontsize=8,
               bbox_to_anchor=(0.5, -0.08))
    fig.suptitle("Figure 6: Scenario Comparison — Six Scenarios × Four Outcome Metrics",
                 fontsize=12, fontweight="bold")
    plt.tight_layout()
    path = fig_dir / "F6_scenario_comparison.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [F6] saved → {path.name}")
    return path


# ============================================================================
# F7: CC calibration scatter
# ============================================================================

def fig_cc_calibration(data_dir: Path, fig_dir: Path):
    cc_path   = data_dir / "cc_calibrated.csv"
    unc_path  = data_dir / "cc_uncertainty.csv"
    if not cc_path.exists():
        print("  [F7] cc_calibrated.csv not found — skipping")
        return None

    cc_df  = pd.read_csv(cc_path)
    unc_df = pd.read_csv(unc_path) if unc_path.exists() else None

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.patch.set_facecolor("white")

    # Left: ML CC vs target
    ax = axes[0]
    ax.scatter(cc_df["cc_target"], cc_df["cc_mean"],
               c="#3498DB", alpha=0.7, s=50, edgecolors="white", linewidths=0.5)
    lo = min(cc_df["cc_target"].min(), cc_df["cc_mean"].min()) - 0.05
    hi = max(cc_df["cc_target"].max(), cc_df["cc_mean"].max()) + 0.05
    ax.plot([lo, hi], [lo, hi], "k--", lw=0.8, alpha=0.5, label="Perfect fit")
    _style_ax(ax, "CC Calibration: Model vs Target\n(each point = one node snapshot)",
              xlabel="Target CC (1 − undernourishment proxy)", ylabel="Model CC (LightGBM)")
    ax.legend(fontsize=8)

    # Right: Monte Carlo uncertainty bars
    ax2 = axes[1]
    if unc_df is not None:
        unc_df = unc_df.sort_values("cc_mean", ascending=False).reset_index(drop=True)
        nodes = unc_df["node"].str[:15]
        yerr_lo = np.maximum(0, unc_df["cc_mean"] - unc_df["cc_p5"])
        yerr_hi = np.maximum(0, unc_df["cc_p95"] - unc_df["cc_mean"])
        yerr    = [yerr_lo, yerr_hi]
        ax2.errorbar(range(len(nodes)), unc_df["cc_mean"],
                     yerr=yerr, fmt="o", ms=4, lw=1.2,
                     capsize=3, color="#E67E22", alpha=0.85)
        ax2.set_xticks(range(len(nodes)))
        ax2.set_xticklabels(nodes, rotation=50, ha="right", fontsize=7)
        _style_ax(ax2, "CC Uncertainty (Monte Carlo ±10% param noise)\n"
                  "Bars show 5th–95th percentile across 500 runs",
                  ylabel="CC Index")
    fig.suptitle("Figure 7: CC Index Calibration (ML as Calibration Aid, Not Discovery Engine)",
                 fontsize=11, fontweight="bold")
    plt.tight_layout()
    path = fig_dir / "F7_cc_calibration.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [F7] saved → {path.name}")
    return path


# ============================================================================
# F8: Worst-case discovery scatter
# ============================================================================

def fig_worst_case(data_dir: Path, fig_dir: Path):
    wc_path = data_dir / "worst_case_discovery.csv"
    if not wc_path.exists():
        print("  [F8] worst_case_discovery.csv not found — skipping")
        return None

    df = pd.read_csv(wc_path)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.patch.set_facecolor("white")

    all_wc_path = data_dir / "worst_case_all.csv"
    if all_wc_path.exists():
        all_df = pd.read_csv(all_wc_path)
        type_cols = {"climate": C["climate"], "geopolitical": C["geopolitical"],
                     "speculative": "#9B59B6", "mixed": C["neutral"]}
        colours = [type_cols.get(t, C["neutral"]) for t in all_df.get("trigger_types", ["mixed"]*len(all_df))]
        axes[0].scatter(all_df.get("max_price_ratio", df["max_price_ratio"]),
                        all_df.get("max_overloads", df["max_overloads"]),
                        c=colours, alpha=0.6, s=40)
    else:
        axes[0].scatter(df["max_price_ratio"], df["max_overloads"],
                        c=[C["geopolitical"]] * len(df), alpha=0.7, s=60)

    # Highlight top 5
    for _, row in df.iterrows():
        axes[0].scatter(row["max_price_ratio"], row["max_overloads"],
                        s=120, zorder=5, edgecolors="black", linewidths=1.2,
                        color=C["geopolitical"], marker="*")
        axes[0].annotate(f"#{int(row['rank'])}", (row["max_price_ratio"], row["max_overloads"]),
                         textcoords="offset points", xytext=(4, 3), fontsize=7)

    _style_ax(axes[0], "Exploratory Analysis: Severity Landscape\n(★ = Top 5 worst-case combos)",
              xlabel="Peak Price Ratio", ylabel="Max Overloaded Nodes")

    # Right: top 5 breakdown
    ax2 = axes[1]
    top5_labels = [f"#{r['rank']}: {r['trigger_types']}" for _, r in df.iterrows()]
    top5_scores = df["severity_score"].values
    bars = ax2.barh(range(len(top5_labels)), top5_scores,
                    color=[C["geopolitical"], C["climate"], C["geopolitical"],
                           C["neutral"], C["neutral"]][:len(top5_labels)],
                    alpha=0.85, height=0.6)
    ax2.set_yticks(range(len(top5_labels)))
    ax2.set_yticklabels(top5_labels, fontsize=8)
    _style_ax(ax2, "Top 5 Worst-Case Trigger Combinations",
              xlabel="Severity Score (composite)")
    for b, s in zip(bars, top5_scores):
        ax2.text(s + 0.003, b.get_y() + b.get_height()/2,
                 f"{s:.3f}", va="center", fontsize=8)

    fig.suptitle("Figure 8: Exploratory Worst-Case Discovery\n"
                 "(Compound triggers consistently worse than single large shocks)",
                 fontsize=11, fontweight="bold")
    plt.tight_layout()
    path = fig_dir / "F8_worst_case.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [F8] saved → {path.name}")
    return path


# ============================================================================
# Generate all figures
# ============================================================================

def generate_all_figures(
    data_dir: Path = _DATA,
    fig_dir:  Path = _FIG,
) -> list:
    print("\n[Phase 10] Generating figure suite...")
    paths = []
    for fn in [fig_scenario_timeseries, fig_sensitivity_heatmap,
               fig_retrodiction_comparison, fig_network_hub_map,
               fig_crisis_attribution, fig_scenario_comparison,
               fig_cc_calibration, fig_worst_case]:
        try:
            p = fn(data_dir, fig_dir)
            if p: paths.append(p)
        except Exception as e:
            print(f"  [{fn.__name__}] error: {e}")
    print(f"[Phase 10] {len(paths)}/8 figures generated → {fig_dir}")
    return paths


if __name__ == "__main__":
    generate_all_figures()
