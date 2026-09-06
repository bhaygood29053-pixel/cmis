# Scout ↔ CMIS Integration Contract

Last reconciled: 2026-08-30

## Boundary

```text
Roberta
  -> X1 Scout / Solana Scout
    -> CMIS
      -> Chain Providers / verified sources
```

Scouts interpret CMIS results. They do not call provider APIs, CMIS databases, or internal intelligence helpers directly, and they do not manufacture missing facts.

The compatibility runtime entry point may remain:

```bash
python -m liquidity_scout.cmis.http
```

The `liquidity_scout` namespace is a migration compatibility identifier, not a separate product/authority layer.

## Capability handshake

```text
GET /v1/cmis/capabilities
```

Capability schema `1` is required. Existing services retain the accepted global minimum `1.8.0`; current CMIS contract is `1.26.0`. The promoted concentration service continues to require CMIS `>=1.9.0`; all-available history requires `>=1.10.0`; normalized X1 identity requires `>=1.11.0`; verified provider-price backfill semantics require `>=1.12.0`; and `instant_x1_scan/v2` requires `>=1.14.0`; `instant_x1_scan/v4` with `x1_current_market_freshness/v2` requires `>=1.21.0`.

Scouts validate service state/callability, chain requirements, Evidence Receipt / Proof Score declarations, risk/proof separation, missing-evidence-is-unknown semantics, and exact promotion metadata.

The core Phase 11 `intelligence_foundation` remains read-only and non-promoted as a group.

## Public service surface

Where the live manifest permits:

```text
asset_lookup
market_report
rank
historical_compare
tokenomics
risk_check
pre_trade_check
verification_evidence
concentration_change_intelligence
concentration_warning_intelligence
bridge_to_xdex_utilization
regulatory_evidence
instant_x1_scan
```

`concentration_change_intelligence` is a separately accepted **Phase 12**, X1-only, bounded/read-only wrapper:

```text
service_contract = concentration_change_intelligence/v1
accepted_conclusion_type = top_account_concentration_change
promotion_scope = cmis_owned_top_account_concentration_change_evidence_by_id
public_service_promoted = true
scout_reliance_promoted = true
execution_authorized = false
```

Solana is unavailable/non-callable/non-promoted for this service.

A Scout must validate these exact fields before dispatch and preserve the returned facts/evidence/proof/limitations without recomputation. The service does not establish unique-holder or beneficial-owner semantics and does not authorize whale/insider/bot/intent/ownership labels.

## Instant X1 Scan

CMIS `1.14.0` promotes X1-only `instant_x1_scan/v2` as a bounded read-only composition service. Scouts must treat it as composition over accepted identity, market, tokenomics, verified CMIS history plus bounded verified provider-price backfill, deterministic risk, and runtime evidence-quality data. Provider backfill is price-only and does not prove archive completeness, source independence, full asset lifetime, or continuity. Omitted X1 RPC coverage is `not_requested`, not a provider-configuration failure. The service creates no new underlying fact authority and preserves explicit unknown/partial holder and current-concentration fields.

Solana advertises this service as unavailable. A Scout must validate exact service contract, chain, callability/read-only state, and `execution_authorized=false` before dispatch.

## Request/response rules

Every request names the chain explicitly. Unsupported chains do not fall back to another chain.

CMIS response statuses such as `ok`, `partial`, `unavailable`, `ambiguous`, conflict, or insufficient evidence are meaningful. Missing evidence remains missing; it is never converted into zero, false, or an LLM estimate.

Fresh accepted CMIS/provider evidence overrides remembered live values.

## Historical comparison usage

Under CMIS `1.10.0+`, X1 Scouts may use the existing `historical_compare` service in three modes:

- `window` — existing explicit 24h / 7d / 30d metric comparison;
- `all_available` — one asset across all verified observations currently stored by CMIS;
- `all_available_pair` — two assets compared only across their overlapping verified CMIS observation window.

Natural requests such as “entire history,” “full history,” “since inception,” or “lifetime history” may select `all_available`; pair mode still requires an explicit second asset. Scouts must preserve CMIS coverage bounds and must not relabel `all_available` as proven complete asset lifetime. `full_asset_lifetime_verified=false` and `continuous_coverage_verified=false` remain authoritative until CMIS proves otherwise. For CMIS `>=1.12.0`, verified provider-price backfill may extend price only and must preserve non-independence, archive/continuity uncertainty, historical stable-quote uncertainty, and non-lifetime-completeness.

## X1

X1 is the mature CMIS surface. Evidence remains scope-specific: pool-, route-, provider-, program-, token-account-, or sample-scoped evidence is not automatically asset-wide/global truth.

The Phase 12 concentration wrapper is explicit-only in Roberta/X1 Scout adoption; it is not an autonomous planner capability merely because the service is callable.

## Solana

Solana Phase 10 is complete as a separate read-only provider path beneath the same CMIS architecture. Exact-mint identity, SPL Token / Token-2022 handling, bounded market/tokenomics/risk/history, and source cross-checks remain capability-specific and fail closed. Solana does not inherit X1 capabilities.

## Evidence, risk, and pre-trade

`verification_evidence` remains selector-bound. Evidence Receipt / Proof Score must be preserved; Proof Score is not risk.

`risk_check` is deterministic and separate from service status/proof strength.

`pre_trade_check` remains analysis only. Advanced route/slippage/fee/simulation facts are available only when independently proven for the exact accepted scope. Missing advanced evidence is not zero-filled.

```text
analysis_only = true
execution_authorized = false
```

A `PASS` is not permission to trade.

## Public/private runtime boundary

The CMIS six-phase public-shell/private-core migration is complete. The public package fails closed when protected private-core implementation is unavailable; Scouts must not rely on a public reconstruction fallback. This deployment boundary does not change service authority or capability semantics.

## Safety

No current Scout or CMIS contract authorizes transaction preparation for execution, signing, broadcasting, custody, live trading, bridge transfer, autonomous execution, or value movement.

**CMIS verifies. Scouts preserve and interpret chain-specific results. Roberta coordinates and explains.**


## Bridge-to-XDEX utilization reliance

For CMIS `>=1.19.0`, X1 Scout may rely on
`bridge_to_xdex_utilization/v1` only when the capability record is bounded,
callable, read-only, public-service promoted, Scout-reliance promoted, and
`execution_authorized=false`.

Scout supplies only exact selector/identity/freshness parameters. It does not
submit bridge evidence, XDEX pool/volume evidence, Pyth/value-basis evidence,
or a utilization result. The protected CMIS runtime resolves the canonical
#410 record and the public contract validates it.

Scout must preserve these boundaries: verified XDEX program-family scope is not
every X1 DEX; bounded zero wSOL.X activity is not global zero activity; bridge
activity is not adoption; liquidity is not volume; no causal inference is
authorized; and no automatic risk conclusion is authorized. Scout must not
call Warp, XDEX, Pyth, or other providers to reconstruct this service or
recompute its ratios.


## CMIS 1.20 cross-chain provenance reliance

X1 Scout may rely on `cross_chain_asset_provenance/v1` only when the live
capability manifest advertises the X1 service as bounded, callable, read-only,
public-service promoted, Scout-reliance promoted, and
`execution_authorized=false`.

Scout supplies only the exact CMIS evidence selector and current X1 asset
id/kind. It must preserve ordered hops, representation depth, dependency labels,
and verification flags exactly as CMIS returns them. Scout must not infer
identity from symbol/name equality, manufacture missing hops, convert bridge or
custody dependency into risk, or infer backing, solvency, safety, adoption,
causality, or current bridge state.

## CMIS 1.26 regulatory evidence reliance

X1 Scout may rely on `regulatory_evidence/v1` only when the live capability
manifest advertises the service as bounded, callable, read-only,
public-service promoted, Scout-reliance promoted, and
`execution_authorized=false`.

Initial promoted scope is deliberately narrow: U.S. GENIUS Act evidence for an
exact X1 mint identity, beginning with the exact USDC.X mint
`B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq`.

Scout supplies only jurisdiction, framework, logical asset selector, exact X1
mint, evaluation time, and maximum evidence age. It must not submit legal text,
issuer claims, regulator status, source material, compliance conclusions,
bridge/custody facts, risk, or a precomputed regulatory record.

Scout must preserve these boundaries:

- proposed rule is not final rule;
- final rule is not effective regulation without separately verified effective state;
- framework/applicability evidence is not issuer or asset compliance;
- underlying USDC evidence does not erase USDC.X bridge/custody/liquidity/redemption dependencies;
- regulatory evidence is not legal advice;
- no automatic risk conclusion;
- no execution authorization.

Missing, stale, future-dated, symbol-only, or exact-mint-mismatched evidence
fails closed.
