# CMIS Project Status — 2026-08-30

## Executive status

CMIS is the deterministic cross-chain market-intelligence backend beneath X1 Scout and Solana Scout.

Canonical authority path:

```text
User / transport
  -> Roberta
    -> Chain Scout
      -> CMIS
        -> Chain Provider / verified source
```

Current accepted CMIS capability contract: **1.13.0**.

Controlled Execution remains unauthorized/not started.

## Accepted service and intelligence state

Accepted on `main`:

- X1 and Solana read-only provider foundations under explicit capability gates;
- Evidence Receipts + Proof Score;
- deterministic market risk and bounded analysis-only pre-trade calculations;
- X1 all-available historical comparison under CMIS `1.10.0`;
- normalized exact-mint X1 identity under `x1_asset_identity/v1` from CMIS `1.11.0`;
- bounded verified-provider historical price backfill semantics under CMIS `1.12.0`;
- bounded X1 `instant_x1_scan/v1` composition under CMIS `1.13.0`;
- first narrow X1 promoted intelligence service `concentration_change_intelligence/v1`;
- internal/read-only descriptive classification, direct wallet-relationship evidence, and concentration-threshold alert evidence, all non-promoted unless separately gated.

Proof Score remains separate from deterministic risk.

Missing evidence remains unknown/unavailable and is never converted into zero, false, or a model estimate.

## Instant X1 Scan

`instant_x1_scan/v1` is X1-only, read-only, composition-only, and fail-closed.

It composes accepted:

- exact identity;
- market evidence;
- tokenomics;
- CMIS-stored verified history;
- deterministic risk;
- runtime evidence-quality metadata.

It does not create new underlying fact authority. Unverified holder or current-concentration fields remain explicit unknown/partial values.

## Oracle V2 provider-gap status

Accepted Oracle V2 evidence currently establishes:

- exact X1 program/state structure;
- six assets × five relay slots;
- verified timestamp unit: Unix milliseconds;
- explicit current-price freshness policy:

```text
max_age_ms = 60000
max_future_skew_ms = 5000
minimum_eligible_slots = 3
```

The latest accepted live run classified all observed relay slots stale.

Therefore:

```text
current_price_use_authorized = false
price_correctness_verified = false
source_independence_verified = false
cmis_provider_promoted = false
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

Relay count is not independent-source count. The next Oracle gate should run only when policy-eligible live slots appear.

## Solana state

Solana remains a bounded read-only provider/runtime foundation.

Accepted work includes exact-mint/token handling, explicit freshness semantics, observed-pair aggregation with coverage limits, and selected cross-source comparison foundations.

Solana does not inherit X1 capabilities by implication, and the current X1-first product roadmap defers broader Solana expansion.

## Roberta dependency state

Roberta's Learning System Phases 1-10 and autonomous source-grounded Learning Plane are accepted.

Operator-local *Mastering Blockchain, Fourth Edition* mastery is complete:

```text
required source stages passed = 14 / 14
final source capstone = passed
```

Repository-accepted prebuilt banks remain through Stage 8 / Market Structure. Runtime-generated Stages 9-14 are mastery evidence under the accepted controller, not separately accepted prebuilt repository banks.

Authoritative read-only autonomous-training telemetry is accepted under `roberta-autonomous-training-telemetry/v1`.

Learning does not create CMIS/provider trust, live-state truth, wallet authority, or execution authority.

## Public-shell/private-core migration closure

The six-phase CMIS public-shell/private-core migration is complete.

Accepted steady state:

- protected CMIS implementation removed from active public branch/tag history;
- public CMIS package boundary contains only the intended public surface;
- required private core remains mandatory;
- missing private core fails closed;
- no public reconstruction fallback is accepted;
- public/private migration does not change service authority, proof/risk semantics, or execution denial.

Historical cleanup closure is documented in `PHASE6_HISTORICAL_GIT_CLEANUP.md`.

## Near-term priority

1. Productize X1-first verified intelligence without weakening evidence gates.
2. Harden Instant X1 Scan consumption through the accepted Roberta/X1 Scout path.
3. Continue holder/wallet semantics and promotion work only through explicit verification gates.
4. Continue Oracle V2 only when freshness-eligible evidence appears.
5. Build Discovery Ledger / Early Warning / Compare work as separately accepted contracts.
6. Preserve Solana read-only maturity while deferring broader product expansion.
7. Keep Controlled Execution locked.

## Core rule

**CMIS verifies changing chain facts and bounded analysis. Chain Scouts interpret those facts. Roberta coordinates and synthesizes them. Missing evidence remains unknown, and no internal implementation or learning state self-promotes into public capability or execution authority.**
