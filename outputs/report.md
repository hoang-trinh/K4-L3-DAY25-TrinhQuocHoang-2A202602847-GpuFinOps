# NimbusAI — GPU Cost Optimization Report

**Period:** monthly  
**Baseline spend:** $27,133  
**Optimized spend:** $14,626  
**Projected savings:** $12,507  (**46%**)

## Savings by lever

| Lever | Savings (USD) |
|---|---|
| Inference (cascade/cache/batch) | $1,212 |
| Purchasing (spot/reserved) | $10,040 |
| Right-size util-lies | $655 |
| Kill idle GPUs | $600 |

## Sustainability

- Energy per query: 0.24 Wh
- Carbon per query: 0.091 gCO2e
- Cheapest+cleanest region: europe-north1

## FinOps Extensions (Your Turn)

### Extension 3: Prompt Caching Economics (`cache_is_worth_it`)
- Break-even reads threshold: 1.39 reads
- Observed avg cache reads: 480.0 reads
- Status: Economically viable (prefix amortization confirmed)

### Extension 4: Reasoning Budget & Energy Footprint
- Reasoning traffic share: 8.4% of total queries
- Reasoning energy share: 94.0% of total Wh
- Routing rule: Gate reasoning behind task complexity threshold; cap at 5% traffic.

_Figures are June-2026 as-of snapshots; re-baseline before acting._