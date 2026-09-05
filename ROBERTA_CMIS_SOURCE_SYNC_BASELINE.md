# ROBERTA ↔ CMIS Source Sync Baseline

Last reconciled: 2026-09-05 (America/New_York)

This is the CMIS-side mirror of the four-repository roadmap/status checkpoint.

## Authority invariant

`User / transport -> ROBERTA -> Chain Scout -> CMIS -> Chain Provider / verified source`

- CMIS owns deterministic freshness-sensitive facts, evidence, Proof Score, risk, historical intelligence, bridge evidence, and provider semantic verification.
- ROBERTA owns orchestration and final synthesis.
- Open PR evidence is not accepted runtime truth.
- Missing evidence remains unknown/unavailable.
- `execution_authorized=false`.

## Repository heads at reconciliation start

```text
ROBERTA public      e1ab51fc5a004652274597de297cc96e85132f08
ROBERTA protected   267aa3b1adb1c49ec11ab88ab53c8d2a83515251
CMIS public         9eea8a13f4d19b3c18021c44b62367a3c1bf425b
CMIS protected      e34353c4a4ce90d1f9da7ffb8f62bee4d03d1456
```

CMIS advanced after that checkpoint through merged Web Discovery PR #478 and this documentation reconciliation; the SHAs above remain the reconciliation-start reference.

## #461 current state

Accepted: #465 fact-time, #466 current USDC.X reserve backing, #468 current USDC.X/USD live equivalence.

Active: PR #470 final five-pool USD-liquidity semantics. Liquidity freshness remains separate under #459.

## #410 current state

Accepted: #409 and PR #467 utilization foundation.

Active: PR #469 final 24h XDEX activity/value-basis evidence. Its exact-head final live workflow is green; merge/reconciliation and later public-service / Scout-reliance promotion are still required before ROBERTA #314 may consume the result.

## Web Discovery current state

Merged internal foundations:

- #472 six-source bounded discovery;
- #474 X1 Explorer structured discovery;
- #476 sanitized network observation;
- #478 operator-controlled passive browser capture.

All remain `DISCOVERED`, non-promoted, and non-authorizing.

## ROBERTA

Opinion v1 and Claim Integrity v1 for X1 asset intelligence/Compare remain accepted. Standalone History is the next ROBERTA Truth Gate. ROBERTA #314 remains blocked on accepted/promoted CMIS cross-chain output.

`execution_authorized=false`
