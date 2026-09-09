# ROBERTA ↔ CMIS Source Sync Baseline

Last reconciled: 2026-09-08 22:33 America/New_York

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
ROBERTA public      b023bce04b0426ff71d66a8c1023cf428a86e60b
ROBERTA protected   f6fdab139b3573939b66ef4a934bb4b59bd362ee
CMIS public         4778da694a3a735c946908fef08bec3664c36107
CMIS protected      9cf490f55eeee12e109343b50b1642a1f15854ff
ROBERTA eval        9fb6cc488b169e00a9654f8a70bdf1b2a520e3dd
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
- `live-smoke-004` is complete: 20/20 runtime OK, 8 PASS, 12 EVIDENCE_REQUIRED, 0 FAIL. The 12 blocked cases are localized to protected ROBERTA current-X1 evidence delegation, not to CMIS. Protected `roberta-core` #89 / PR #90 is the active remediation; after deterministic acceptance and five-repo runtime sync, the next evaluation proof is `live-smoke-005` on the same 20-case plan.

## Protected cores

Public roadmap/evidence changes do not silently mutate protected runtime behavior. Protected implementation changes remain separately reviewed.

`execution_authorized=false`
