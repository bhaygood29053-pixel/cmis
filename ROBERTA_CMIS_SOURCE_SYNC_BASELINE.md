# Roberta ↔ CMIS Source Sync Baseline

Last reconciled: 2026-09-02 (America/New_York)

This file is the compact cross-project synchronization baseline and is intentionally mirrored byte-for-byte in the public ROBERTA and CMIS repositories. Repository-local roadmap, contract, status, and protected-core documents remain authoritative for implementation details.

## Product identity and authority invariant

- **ROBERTA — Verified On-Chain Intelligence** is the canonical public-facing product name.
- Canonical authority path: `User / transport -> ROBERTA -> Chain Scout -> CMIS -> Chain Provider / verified source`.
- ROBERTA owns orchestration, policy coordination, specialist selection, learning coordination, approval boundaries, and final synthesis.
- Chain Scouts own chain-specific planning, contract validation, and interpretation; they do not manufacture blockchain facts.
- CMIS owns deterministic freshness-sensitive facts, evidence, Evidence Receipts, Proof Scores, risk, capability state, historical intelligence, burn arithmetic, and bounded analysis-only calculations.
- Missing evidence remains unknown/unavailable; it is never converted into zero, false, infinity, or a model estimate.
- Proof Score remains separate from risk.
- Controlled Execution remains locked/not started. `execution_authorized=false` remains invariant.

## Accepted repository heads

- CMIS public `main`: `38e0b6c5ae231f4e8204204082c8baf850998da0`
- protected `cmis-core` `main`: `6a1befc49162cb121c2be86e6ccc755950793d15`
- ROBERTA public `main`: `01ccd6d5d3950709eed9108832aa6812091bfda2`
- protected `roberta-core` `main`: `bcd2be575a70f6ad9de43d38054e52ce8938eb54`

## X1 Burn Intelligence — accepted v1 architecture

Burn Intelligence is now a first-class CMIS-owned capability.

```text
User
  -> ROBERTA
    -> X1 Scout
      -> CMIS burn_intelligence/v1
        -> accepted CMIS tokenomics / burn-scanner evidence
          -> X1 provider / verified source
```

### CMIS authority

CMIS capability contract `1.15.0` promotes:

```text
service = burn_intelligence
service_contract_version = burn_intelligence/v1
chain = x1
state = bounded
callable = true
read_only = true
public_service_promoted = true
scout_reliance_promoted = true
execution_authorized = false
```

Accepted implementation gates:

- CMIS public PR #389 — first-class `burn_intelligence/v1` contract and capability promotion;
- protected `cmis-core` PR #12 — runtime dispatch through the existing deterministic tokenomics/burn-evidence path;
- no second burn scanner, parser, arithmetic path, circulating-supply inference path, or burn-time valuation engine was introduced.

CMIS owns and preserves:

- cumulative verified-observed burn and observed burn-event totals;
- explicit `lifetime_total_burn_verified`;
- 1h / 24h / 7d / 30d windows;
- burn and mint amounts/event counts for verified windows;
- 24h / 7d / 30d equal-period comparison states and percentage changes;
- null percent semantics for non-numeric zero-base/insufficient-coverage states;
- burn-to-emission ratio, net issuance, and issuance state;
- coverage bounds and verification state;
- independently gated circulating-supply context;
- exact burn-time valuation and valuation completeness;
- Evidence Receipt / Proof Score lineage and explicit unknowns.

Verified-observed cumulative burn is **not** a lifetime-total claim unless archive/signature/history completeness independently proves `lifetime_total_burn_verified=true`.

### X1 Scout

ROBERTA public PR #295 hardened `x1_burn_intelligence/v1`. ROBERTA public PR #304 switched X1 Scout from generic CMIS `tokenomics` consumption to the dedicated CMIS `burn_intelligence/v1` service.

X1 Scout:

- requires the accepted CMIS 1.15.0 Burn Intelligence capability before dispatch;
- requires exact X1 mint agreement and the dedicated CMIS service contract;
- preserves CMIS burn metrics without recomputation;
- preserves unavailable/partial/null states;
- rejects weakened coverage/comparison semantics and execution authorization;
- exposes the validated `x1_burn_intelligence/v1` product on the Scout report.

Human ROBERTA exposes the first-class workflow as:

```text
/burn <asset>
```

### Canonical ROBERTA Decision Object

Protected `roberta-core` PR #23 added `x1_burn_intelligence` to `roberta_decision/v1`; PR #24 validated that protected core against the accepted public Burn Intelligence shell.

Both Human ROBERTA and Machine ROBERTA consume the same canonical burn facts. Neither renderer recalculates burn totals, comparison percentages, circulating supply, historical valuation, risk, or Proof Score.

## Burn Intelligence v1 completion state

The X1 Burn Intelligence v1 productization milestone is **accepted and complete** across CMIS public/protected runtime and ROBERTA public/protected decision layers.

Future burn work is evidence-driven only. In particular:

- do not claim lifetime burn until complete lifetime/archive evidence exists;
- do not treat transfers to presumed dead addresses as burns without accepted burn semantics;
- do not derive circulating supply from burn totals;
- do not value historical burns with current, nearest, or interpolated prices;
- do not create a burn-derived trade recommendation or risk score;
- do not widen Burn Intelligence into Controlled Execution.

## Next synchronized product direction

Burn Intelligence no longer blocks the roadmap. The next intelligence work should build on separately accepted evidence foundations such as Discovery / first-observation history, WHAT CHANGED?, and Early Warning rather than adding speculative Burn Intelligence features.

## Core sync rule

**CMIS verifies changing chain facts. X1 Scout validates and projects accepted CMIS contracts. ROBERTA orchestrates and explains them. Human and Machine ROBERTA share the same canonical Decision Object. No layer above CMIS may silently recompute Burn Intelligence or promote missing evidence into fact.**

`execution_authorized=false`
