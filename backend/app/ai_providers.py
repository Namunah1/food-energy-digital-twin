"""
ai_providers.py
----------------
The AIProvider architecture for the AI Policy Advisor.

CRITICAL CONSTRAINT: providers explain results, they never compute them.
Every provider's `explain()` receives a `grounding` dict that was already
populated entirely from real backend simulation output (model_bridge.py
calling the actual ABM). Providers may only rephrase/summarize numbers that
are already in `grounding` -- they must not introduce new figures.

- MockProvider: always available. Returns a structured, template-based
  explanation built directly from the grounding dict. No network call.
- OpenAIProvider / AnthropicProvider / GeminiProvider: real providers, each
  gated on the presence of its API key as an environment variable. If the
  key isn't set, is_configured() is False and the advisor falls back to
  Mock automatically. Activating a real LLM later is just setting the key
  -- no code changes needed.
"""
from __future__ import annotations

import os
import json
from abc import ABC, abstractmethod
from typing import Optional

SYSTEM_PROMPT = (
    "You are a policy-advisor explanation layer for a food-energy systemic-risk "
    "simulation platform. You will be given (1) the user's question and (2) a JSON "
    "'grounding' object containing the ONLY numbers you may reference -- they come "
    "from a real agent-based model run, already computed. "
    "Rules: never invent, estimate, or adjust any number not present in the grounding "
    "JSON. Never perform your own calculations. If the grounding doesn't cover part of "
    "the question, say so explicitly rather than guessing. Write 3-6 sentences, plain "
    "language, suitable for a policymaker. Always note this is one simulation run, not "
    "a certainty."
)


class AIProvider(ABC):
    name: str = "base"

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def explain(self, question: str, grounding: dict) -> str: ...


class MockProvider(AIProvider):
    """
    Deterministic, template-based explanation from the grounding dict.
    Always available -- this is the default provider until a real API key
    is configured. Not an LLM; produces structured prose from real numbers.
    """
    name = "mock"

    def is_configured(self) -> bool:
        return True

    def explain(self, question: str, grounding: dict) -> str:
        intent = grounding.get("intent")
        d = grounding.get("data", {})

        if intent == "country_shock":
            return (
                f"Simulating a {d['severity']}% climate/drought shock targeted at "
                f"{d['country']}, starting year {d['start_step']} of a {d['n_steps']}-year run: "
                f"{d['country']}'s own food security ratio (σ) moves to {d['country_food_security']:.2f} "
                f"({d['country_status']}). Globally, peak population at risk rises from "
                f"{d['baseline_par_bn']:.2f}bn (baseline) to {d['scenario_par_bn']:.2f}bn, and the peak "
                f"food price index moves from {d['baseline_price_index']:.2f} to {d['scenario_price_index']:.2f}. "
                f"This is one seeded simulation run of the real ABM, not a certainty -- rerunning with a "
                f"different seed or duration would shift the exact figures."
            )
        if intent == "global_energy_shock":
            return (
                f"Simulating a global energy-crisis shock (severity {d['severity']}%, all nodes) over "
                f"{d['n_steps']} years: peak population at risk moves from {d['baseline_par_bn']:.2f}bn "
                f"(baseline) to {d['scenario_par_bn']:.2f}bn, peak food price index from "
                f"{d['baseline_price_index']:.2f} to {d['scenario_price_index']:.2f}, and peak trade "
                f"collapse from {d['baseline_tc']:.2f} to {d['scenario_tc']:.2f}. Energy and food are "
                f"coupled in this model (ε_EF elasticity), so an energy shock alone raises food prices "
                f"even with no direct food-side trigger. One simulation run, not a certainty."
            )
        if intent == "ranking_aid":
            rows = "; ".join(f"{r['name']} (σ={r['food_security']:.2f})" for r in d["ranked"][:8])
            return (
                f"Ranking all {d['total_nodes']} modeled nodes by current food security ratio (σ) under "
                f"the baseline (no-shock) trajectory, the most at-risk are: {rows}. Lower σ means less "
                f"of the node's food need is met relative to its coping capacity; nodes below 0.8 are in "
                f"the 'crisis' band used elsewhere on this platform. This reflects the model's current "
                f"baseline state, not a live humanitarian assessment."
            )
        if intent == "policy_comparison":
            rows = "; ".join(
                f"{r['label']}: peak PAR {r['max_par_bn']:.2f}bn, peak price index {r['max_price_index']:.2f}"
                for r in d["ranked"]
            )
            best = d["ranked"][0]
            return (
                f"Comparing the three response levers against the same geopolitical-freeze shock set "
                f"(S2), each run independently: {rows}. Of these, {best['label']} produces the lowest "
                f"peak population at risk ({best['max_par_bn']:.2f}bn) in this run. This compares only "
                f"the three interventions already implemented in the model (reserves, trade "
                f"diversification, trader regulation/renewables) -- not every possible policy."
            )
        if intent == "baseline_query":
            return (
                f"Under the current baseline (no-shock) trajectory over {d['n_steps']} years: global food "
                f"security (σ) is {d['gfs']:.2f}, population at risk is {d['par_bn']:.2f}bn, food price "
                f"index is {d['price_index']:.2f}, and {d['n_overload']} of 35 nodes are in LFBB stress "
                f"overload. This is the model's structural baseline, not a shock scenario."
            )
        if intent == "experiment":
            mode_phrase = {
                "historical": "historical reconstruction",
                "counterfactual": "counterfactual experiment",
                "projection": "scenario projection",
            }.get(d["mode"], d["mode"])
            parts = [
                f"This {mode_phrase} runs {d['anchor_year']} \u2192 {d['target_year']} "
                f"({d['n_steps']} years)."
            ]
            if not d["has_shock"]:
                parts.append("No shock was injected -- this shows the world's own baseline trajectory over that window.")
            else:
                parts.append(
                    f"{d['shock_count']} trigger(s) applied. {d['total_affected']} nodes were genuinely "
                    f"affected (isolated from pre-existing structural stress by diffing against an "
                    f"identical no-shock run of the same seed)."
                )
                if d["top_affected"]:
                    parts.append(f"Most affected, in order: {', '.join(d['top_affected'])}.")
                parts.append(
                    f"Peak food price index: {d['final_price_index']} vs {d['baseline_price_index']} "
                    f"baseline. Peak population at risk: {d['final_par_bn']:.2f}bn vs "
                    f"{d['baseline_par_bn']:.2f}bn baseline."
                )
            if d["has_uncertainty"] and d["uncertainty_price"]:
                up = d["uncertainty_price"]
                parts.append(
                    f"Across the Monte Carlo ensemble, peak price index came out to "
                    f"{up['mean']} \u00b1 {up['std']} (90% range {up['p5']}-{up['p95']}) -- "
                    f"treat that range as the honest answer, not the single point estimate."
                )
            ep = d.get("episode_meta") or {}
            if ep.get("kind") == "descriptive_historical":
                parts.append(f"Note: {ep.get('note', '')}")
            parts.append("This is one simulation of the real ABM, not a certainty.")
            return " ".join(parts)

        if intent == "custom_projection":
            anchor = "real calibrated data" if d["used_real_anchor"] else "the model's own simulated state"
            top_attr = "; ".join(
                f"{a['node']} (food stress {a['food_stress_pct']:.0f}%, contagion {a['contagion_pct']:.0f}%)"
                for a in d["attribution"][:3]
            ) if d["attribution"] else "no single node dominated the outcome"
            return (
                f"Projecting from {d['start_year']} ({anchor}) to {d['target_year']} ({d['n_steps']} years), "
                f"across {d['n_mc']} Monte Carlo runs (different random seeds, same shocks): peak food price "
                f"index comes out to {d['price_index_mean']:.2f} ± {d['price_index_std']:.2f} "
                f"(90% range {d['price_index_p5']:.2f}-{d['price_index_p95']:.2f}), versus "
                f"{d['baseline_price_index']:.2f} with no shocks applied over the same horizon. Peak "
                f"population at risk: {d['par_bn_mean']:.2f}bn ± {d['par_bn_std']:.2f}bn, versus "
                f"{d['baseline_par_bn']:.2f}bn baseline. The nodes driving this outcome most: {top_attr}. "
                f"This spread reflects genuine model uncertainty (stochastic elements in trade/price "
                f"resolution across seeds) -- treat the range, not the point estimate, as the honest answer."
            )
        return (
            "I couldn't map this question to one of the simulation queries this advisor supports yet "
            "(country-specific shocks, global energy shocks, aid-priority ranking, policy-lever "
            "comparison, or a baseline summary). Try rephrasing, or use the Scenario Lab directly for "
            "full control."
        )


class OpenAIProvider(AIProvider):
    name = "openai"
    MODEL = "gpt-4o-mini"

    def is_configured(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY"))

    def explain(self, question: str, grounding: dict) -> str:
        if not self.is_configured():
            raise RuntimeError("OPENAI_API_KEY not set")
        import requests
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
            json={
                "model": self.MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Question: {question}\n\nGrounding JSON:\n{json.dumps(grounding)}"},
                ],
                "max_tokens": 400,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


class AnthropicProvider(AIProvider):
    name = "anthropic"
    MODEL = "claude-sonnet-4-6"

    def is_configured(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    def explain(self, question: str, grounding: dict) -> str:
        if not self.is_configured():
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        import requests
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.MODEL,
                "max_tokens": 400,
                "system": SYSTEM_PROMPT,
                "messages": [
                    {"role": "user", "content": f"Question: {question}\n\nGrounding JSON:\n{json.dumps(grounding)}"},
                ],
            },
            timeout=30,
        )
        resp.raise_for_status()
        blocks = resp.json().get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")


class GeminiProvider(AIProvider):
    name = "gemini"
    MODEL = "gemini-2.0-flash"

    def is_configured(self) -> bool:
        return bool(os.environ.get("GOOGLE_API_KEY"))

    def explain(self, question: str, grounding: dict) -> str:
        if not self.is_configured():
            raise RuntimeError("GOOGLE_API_KEY not set")
        import requests
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.MODEL}:generateContent"
            f"?key={os.environ['GOOGLE_API_KEY']}",
            json={
                "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": [
                    {"parts": [{"text": f"Question: {question}\n\nGrounding JSON:\n{json.dumps(grounding)}"}]},
                ],
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


_PROVIDERS: list[AIProvider] = [AnthropicProvider(), OpenAIProvider(), GeminiProvider(), MockProvider()]


def get_active_provider() -> AIProvider:
    """First configured real provider wins; MockProvider is always last as fallback."""
    for p in _PROVIDERS:
        if p.is_configured():
            return p
    return MockProvider()


def list_providers() -> list[dict]:
    return [{"name": p.name, "configured": p.is_configured()} for p in _PROVIDERS]
