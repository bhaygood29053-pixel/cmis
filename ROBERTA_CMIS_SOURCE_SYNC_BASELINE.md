# ROBERTA ↔ CMIS Source Sync Baseline

Last reconciled: 2026-09-08 23:15 America/New_York

This is the CMIS-side mirror of the four-repository roadmap/status checkpoint. The independent `roberta-eval` repository is tracked as an evaluation consumer outside the production authority chain.

## Authority invariant

`User / transport -> ROBERTA -> Chain Scout -> CMIS -> Chain Provider / verified source`

- CMIS owns deterministic facts, freshness, evidence, Proof Score, risk, history, bridge evidence, and provider semantic verification.
- ROBERTA owns orchestration and final synthesis.
- `roberta-eval` evaluates observed behavior; it does not manufacture provider truth or production authority.
- Open PR evidence is not accepted truth.
- Missing evidence remains unknown/unavailable.
- `execution_authorized=false`.

## Observed heads before this documentation reconciliation

```text
ROBERTA public      83aaf290c665f268fb7966e91f3d8177e4c111fd
ROBERTA protected   91617f8091e7f69094f511956df3481d47f8f66c
CMIS public         1c791eca48b3e9687daac4f5a22db8061e4ced88
CMIS protected      d79b684981bd431f1add5a40fc529cc5d6487720
ROBERTA eval        be1e37267081b8daa5b17c41a4d4575661517622
```

These SHAs were observed immediately before this reconciliation write; documentation commits created by the reconciliation advance the affected `main` branches afterward.

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

- provider-gap track #30 (**active umbrella**);
- FortiBlox token-price fact-time freshness #567 (**primary concrete provider gate**);
- Warp historical-retention/message-counter work where still open;
- delayed-departure / X1.Ninja research;
- Theo machine-transport work;
- other historical-provider investigations.

All remain fail closed until separately accepted.

## ROBERTA / Evaluation state

- ROBERTA consumes the accepted CMIS 1.27 surface through X1 Scout under existing authority boundaries.
- Public ROBERTA #401 + protected `roberta-core` #86 restore stateless/threaded bridge compatibility.
- `roberta-eval` LAB #21 and LAB #22 are accepted.
- `live-smoke-004` is preserved: 20/20 runtime OK, 8 PASS, 12 EVIDENCE_REQUIRED, 0 FAIL. The Evaluation Laboratory is now **PAUSED BY OWNER**. Protected `roberta-core` #89 / PR #90 remains OPEN / UNACCEPTED historical remediation and is not an active product blocker; no `live-smoke-005` or eval-driven merge work should proceed until explicitly resumed.

## Protected cores

Public roadmap/evidence changes do not silently mutate protected runtime behavior. Protected implementation changes remain separately reviewed.

`execution_authorized=false`
