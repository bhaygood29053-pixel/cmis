# ROBERTA ↔ CMIS Source Sync Baseline

Last reconciled: 2026-09-08 (America/New_York)

This is the CMIS-side mirror of the four-repository roadmap/status checkpoint. The independent `roberta-eval` repository is tracked as an evaluation consumer outside the production authority chain.

## Authority invariant

`User / transport -> ROBERTA -> Chain Scout -> CMIS -> Chain Provider / verified source`

- CMIS owns deterministic facts, freshness, evidence, Proof Score, risk, history, bridge evidence, and provider semantic verification.
- ROBERTA owns orchestration and final synthesis.
- `roberta-eval` evaluates observed behavior; it does not manufacture provider truth or production authority.
- Open PR evidence is not accepted truth.
- Missing evidence remains unknown/unavailable.
- `execution_authorized=false`.

## Repository heads at this reconciliation

```text
ROBERTA public      4c872b4ac9fb25dda0994632e9e2f7dc4cc8cdfc
ROBERTA protected   18c6d82377876c0627edb741e5c36f1f339dbbdc
CMIS public         e2a53c94f481ecec4a4f9e1e7051684203e32299
CMIS protected      9cf490f55eeee12e109343b50b1642a1f15854ff
ROBERTA eval        ee624173a1af899a3290b456fb4056ef2e5e35bb
```

Documentation reconciliation commits may advance these heads after this checkpoint.

## Current accepted CMIS state

- capability contract `1.27.0`;
- Instant X1 Scan v6;
- universal `cmis_response_freshness/v1`;
- accepted X1 history, exact-mint identity, Burn, Discovery, concentration warning / Early Warning, deterministic risk, and bounded pre-trade analysis;
- Bridge-to-XDEX and cross-chain asset provenance promoted for X1 Scout reliance;
- `trade_price_impact_intelligence/v1`;
- provider-scoped `large_trade_discovery/v1`;
- freshness-aware `regulatory_evidence/v1`;
- internal Web Discovery through X1 Agents Radio structured discovery, direct X1 RPC corroboration, and exact program/upgrade semantic verification.

## Roadmap boundary changes

### XONE/XNT

XONE/XNT Conversion Intelligence is **RETIRED / HISTORICAL** by Issue #628 / merge #629.

Accepted evidence, contracts, and regressions remain for auditability. There is no active XONE/XNT lead-recovery, snapshot/allocation-binding, issuance/vesting/unlock, public-service promotion, or X1-Scout promotion gate. Retirement does not prove or disprove a XONE→XNT conversion mechanism.

### X1Scroll

Issue #458 / draft PR #549 is **ON HOLD**.

The required X1Scroll API key is unavailable. Do not merge or promote the historical fallback until the key exists and the exact live archival `getTransaction` gate passes. Deterministic CI is not a substitute for that live evidence.

## Current parallel work

- provider-gap track #30;
- FortiBlox token-price fact-time freshness #567;
- Warp historical-retention/message-counter work where still open;
- delayed-departure / X1.Ninja research;
- Theo machine-transport work;
- other historical-provider investigations.

All remain fail closed until separately accepted.

## ROBERTA / Evaluation state

- ROBERTA consumes the accepted CMIS 1.27 surface through X1 Scout under existing authority boundaries.
- Public ROBERTA #401 + protected `roberta-core` #86 restore stateless/threaded bridge compatibility.
- `roberta-eval` LAB #21 and LAB #22 are accepted.
- The next evaluation proof is a 20-case repaired-runtime live rerun followed by LAB #22 diagnostics; no live-quality PASS is assumed before those results exist.

## Protected cores

Public roadmap/evidence changes do not silently mutate protected runtime behavior. Protected implementation changes remain separately reviewed.

`execution_authorized=false`
