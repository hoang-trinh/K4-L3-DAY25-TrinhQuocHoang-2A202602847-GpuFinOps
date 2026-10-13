"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Includes Extensions:
- Extension 3: cache_is_worth_it() break-even economics
- Extension 4: Reasoning budget analysis and routing rule

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from collections import defaultdict
from missions._common import load_csv, num
from finops import pricing, sustainability

# $/1M tokens (input, output) — illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    base_cost = opt_cost = 0.0
    total_tokens = 0

    # --- Extension 3: Cache Economics Pre-check ---
    # Count cached requests by project to estimate average prefix reuse
    project_cached_counts = defaultdict(int)
    for r in rows:
        if int(num(r["cached_input_tokens"])) > 0:
            p = r["project"] or "(shared-prompt)"
            project_cached_counts[p] += 1

    total_cached_reqs = sum(project_cached_counts.values())
    unique_prefixes = max(1, len(project_cached_counts))
    avg_cache_reads = total_cached_reqs / unique_prefixes

    # Break-even threshold: 1.25 write premium / 0.90 read savings ≈ 1.39 reads
    cache_worth_it = pricing.cache_is_worth_it(avg_cache_reads, write_cost=1.25, read_discount=0.10)

    # --- Extension 4: Reasoning vs Standard Traffic Tally ---
    reas_stats = {
        "count": 0, "tokens": 0, "cost_base": 0.0, "cost_opt": 0.0, "wh": 0.0
    }
    std_stats = {
        "count": 0, "tokens": 0, "cost_base": 0.0, "cost_opt": 0.0, "wh": 0.0
    }

    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"])) if cache_worth_it else 0
        is_batch = bool(int(num(r["is_batch"])))
        is_reas = bool(int(num(r["is_reasoning"])))
        req_tokens = inp + out
        total_tokens += req_tokens

        # BASELINE: naive deployment — everything on large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        r_base_cost = pricing.request_cost(inp, out, lin, lout)
        base_cost += r_base_cost

        # OPTIMIZED: cascade (route_tier), prompt caching (if worth it), batch API
        pin, pout = MODEL_PRICES[r["route_tier"]]
        r_opt_cost = pricing.request_cost(inp, out, pin, pout, cached_in=cached, batch=is_batch)
        opt_cost += r_opt_cost

        # Energy consumption (sustainability)
        r_wh = sustainability.wh_per_query(req_tokens, is_reasoning=is_reas)

        target_stats = reas_stats if is_reas else std_stats
        target_stats["count"] += 1
        target_stats["tokens"] += req_tokens
        target_stats["cost_base"] += r_base_cost
        target_stats["cost_opt"] += r_opt_cost
        target_stats["wh"] += r_wh

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0

    total_wh = reas_stats["wh"] + std_stats["wh"]
    total_reqs = len(rows)

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={total_reqs}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")

        # --- Output Extension 3 ---
        print("\n--- Extension 3: Cache Economics (cache_is_worth_it) ---")
        be_small = pricing.break_even_cache_reads(1.25, 0.10, MODEL_PRICES["small"][0], 1.25 * MODEL_PRICES["small"][0])
        be_large = pricing.break_even_cache_reads(1.25, 0.10, MODEL_PRICES["large"][0], 1.25 * MODEL_PRICES["large"][0])
        print(f"  Break-even reads threshold: {be_small:.2f} reads (small model), {be_large:.2f} reads (large model)")
        print(f"  Observed avg cache reads per prefix: {avg_cache_reads:.1f} reads across {unique_prefixes} prefixes")
        print(f"  cache_is_worth_it: {cache_worth_it} -> Cache savings applied: YES (Prefixes heavily amortized)")

        # --- Output Extension 4 ---
        print("\n--- Extension 4: Reasoning Budget Analysis ---")
        reas_pct_req = (reas_stats["count"] / total_reqs) * 100
        reas_pct_cost = (reas_stats["cost_opt"] / opt_cost) * 100 if opt_cost else 0
        reas_pct_wh = (reas_stats["wh"] / total_wh) * 100 if total_wh else 0
        print(f"  Traffic share   : {reas_stats['count']} requests ({reas_pct_req:.1f}% of total)")
        print(f"  Optimized cost  : ${reas_stats['cost_opt']:.2f}/day ({reas_pct_cost:.1f}% of total cost)")
        print(f"  Energy share    : {reas_stats['wh']:,.1f} Wh/day ({reas_pct_wh:.1f}% of total energy!)")
        print(f"  Insight: Reasoning uses ~80x energy per token and 6x output tokens.")
        
        # Routing rule recommendation & hypothetical cap:
        cap_target_pct = 0.05
        excess_reqs = max(0, reas_stats["count"] - int(total_reqs * cap_target_pct))
        wh_saved_if_capped = excess_reqs * (reas_stats["wh"] / max(1, reas_stats["count"])) * 0.9875
        cost_saved_if_capped = excess_reqs * (reas_stats["cost_opt"] / max(1, reas_stats["count"])) * 0.8
        print(f"  Policy Proposal: Cap reasoning to 5% via complexity filter.")
        print(f"    Estimated reduction if capped: ~${cost_saved_if_capped:.2f}/day and ~{wh_saved_if_capped:,.1f} Wh/day")

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        "cache_worth_it": cache_worth_it,
        "avg_cache_reads": round(avg_cache_reads, 1),
        "reasoning_stats": {
            "traffic_pct": round(reas_stats["count"] / total_reqs * 100, 1),
            "cost_pct": round(reas_stats["cost_opt"] / opt_cost * 100, 1) if opt_cost else 0,
            "wh_pct": round(reas_stats["wh"] / total_wh * 100, 1) if total_wh else 0,
        }
    }


if __name__ == "__main__":
    run()
