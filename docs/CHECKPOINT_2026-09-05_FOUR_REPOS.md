# Four-Repository GitHub Checkpoint — 2026-09-05

## Accepted implementation heads at checkpoint start

| Repository | Visibility | Accepted implementation head |
| --- | --- | --- |
| `cmis` | public | `e3fcaa28c32143de03a88bebe1f3626e22a46573` |
| `cmis-core` | private | `e84a352f12fa2b5291a98de61603f8dece577d44` |
| `roberta-langgraph` | public | `548bf70360ecb928002b8d9fce6cc8a673b1919e` |
| `roberta-core` | private | `6627e756427f6270a7f32a243e40ad4db4df3c71` |

## What is stable now

CMIS PR #465 is merged. The X1.Ninja liquidity revaluation/fact-time side of #461 has five verified same-fact events across five distinct pools and `liquidity_fact_time_verified=true`.

ROBERTA Opinion v1 and Claim Integrity remain accepted, including Compare Claim Integrity. Protected/public boundaries remain intact in both projects.

## What remains open

CMIS PR #466 remains research/verification work for current USDC.X value equivalence. Its retained-message liability interpretation is not accepted. Final X1.Ninja USD-liquidity semantics and liquidity freshness remain unpromoted.

ROBERTA must not upgrade the #461 liquidity claim until CMIS completes the remaining exact evidence gates.

## Safety boundary

```text
execution_authorized=false
```

No transaction construction, signing, broadcasting, custody, trading, bridge execution, or autonomous value movement is authorized by this checkpoint.
