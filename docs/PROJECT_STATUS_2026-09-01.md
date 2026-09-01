# CMIS Project Status — 2026-09-01

## Executive status

CMIS is in active X1 productization. Public `main` is at `dfae29c48ad013e12ea3498dfcd63cc3df855783` at this reconciliation. The capability contract remains `1.13.0`; Instant X1 Scan, all-available history, exact-mint X1 identity, verified provider-price backfill semantics, deterministic burn metrics, scanner time-coverage wiring, and deterministic circulating-supply evidence are accepted on `main`.

The public-shell/private-core migration is complete. Protected implementation stays in `cmis-core`; public boundaries fail closed rather than reconstruct protected runtime logic. Controlled execution remains unauthorized.

## Accepted X1 product state

Accepted on `main`:

- `historical_compare` supports explicit windows plus `all_available` and `all_available_pair` verified-observation modes;
- `x1_asset_identity/v1` uses exact mint as the fungible identity root;
- bounded verified-provider historical price backfill remains price-only and explicitly incomplete for lifetime/archive/continuous coverage;
- `instant_x1_scan/v1` is X1-only, read-only, composition-only, and fail-closed;
- deterministic burn metrics cover 1h/24h/7d/30d observed windows plus 24h/7d/30d period-over-period burn change;
- scanner evidence supplies verified fact-time coverage to CMIS tokenomics burn metrics;
- deterministic circulating supply is exposed only when the excluded-token-account universe and balances are completely and independently verified at compatible observation state;
- verified current total supply remains available even if circulating supply is unavailable;
- Oracle V2 freshness governance remains evidence-only and does not authorize a current-price provider.

## Active blockers and pending work

### PR #377 — burn-time valuation

Open/mergeable at reconciliation. This is the final major planned burn-intelligence valuation layer. It requires exact compatible historical price evidence at burn fact time and keeps native/XNT and USD valuation completeness separate. No nearest/current/interpolated substitute is allowed.

### PR #363 — delayed Ninja departure evidence

Open and mergeable at exact head `208756f4880a9d6e47d377b19abab37701a83f2a`.

- Liquidity Scout tests: PASS.
- X1.Ninja Delayed Vault Departure Evidence run #16: FAIL.
- Five independent verified departures remain required.
- Fixed 900-second pre-BEFORE lookback and max 100 signatures per exact vault remain unchanged.
- Routed/multi-AMM ambiguity remains fail-closed unless a separately reviewed classifier change is proven.
- PR #371 and PR #376 routed diagnostics/target-leg proof are integrated into the #363 branch, not accepted as a general classifier on `main`.

Do not merge #363 or weaken its thresholds merely to obtain green CI.

### Discovery Ledger — public #365 + private `cmis-core` #6

Both remain pending. The public PR is contract-only; protected implementation is correctly located in `cmis-core`. Private-core local validation is strong, but required private GitHub Actions acceptance remains blocked by the pre-step runner/startup failure. Do not move protected source back into the public shell to work around CI.

### Issue #374 — automated-order/routed execution families

Open and diagnostic-only. Current evidence can prove routed target-leg topology for a bounded set, but TWAP, limit, take-profit, stop-loss, or other execution-family labels require separate family-specific deterministic evidence. `classification_change_authorized=false` remains authoritative.

## Current roadmap

1. Finish PR #377 burn-time valuation and close the remaining burn-intelligence evidence gap.
2. Resolve PR #363 with the existing live-evidence threshold and fail-closed semantics; inspect failures rather than lowering the gate.
3. Restore private-core CI acceptance for `cmis-core` #6 and complete Discovery Ledger public/private acceptance.
4. Add Scout-facing Discovery/first-observation workflows only after the ledger foundation is accepted.
5. Build deterministic WHAT CHANGED? and Early Warning evidence on accepted Discovery/history primitives.
6. Accumulate quote-to-executed-swap and realized-slippage evidence before defining any expected-slippage contract.
7. Continue X1 provider-gap/oracle evidence work without promoting stale or semantically incomplete sources.
8. Maintain Solana as a bounded read-only secondary surface; no X1 capability inheritance.
9. Keep Controlled Execution locked/not started.

## Roberta dependency state

Roberta public `main` has already adopted Instant X1 Scan and first-class X1 Compare through X1 Scout. Roberta's planned BURN workflow should consume CMIS burn evidence only after the relevant CMIS contract is accepted and Scout adoption is explicitly gated. Roberta must not recompute CMIS burn, valuation, history, risk, or provider facts.

## Safety boundary

`read_only=true` for the evidence work described here. `execution_authorized=false`. No roadmap item authorizes transaction construction, signing, broadcasting, custody, trading, bridge movement, or autonomous value movement.
