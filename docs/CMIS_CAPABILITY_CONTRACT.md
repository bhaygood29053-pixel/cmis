# Scout ↔ CMIS Capability Contract

Last reconciled: 2026-08-26

CMIS publishes machine-readable service eligibility at:

```text
GET /v1/cmis/capabilities
```

This endpoint belongs to the **Chain Scout ↔ CMIS** boundary. Roberta does not call providers directly and does not perform provider-specific capability discovery.

## Contract identity

Accepted baseline:

- capability schema: `1`
- global existing-service minimum: `1.8.0`
- current CMIS contract: `1.12.0`
- request path: `/v1/cmis`
- Evidence Receipt schema: `1`
- Proof Score schema: `1`
- intelligence-foundation schema: `1`
- intelligence-evidence schema: `1`

The flat `version`, `supported_services`, `supported_chains`, and `known_chains` fields remain compatibility metadata. Service eligibility is determined from validated per-chain service records plus the evidence-quality and intelligence-foundation declarations.

## Public service capability states

Each known chain classifies each runtime-advertised public service as `supported`, `bounded`, `partial`, or `unavailable`, with explicit `callable`, `requirements`, and `limitations` fields.

A capability state describes service eligibility, not provider health and not a guarantee that an individual request returns `ok`. Request-time CMIS responses remain authoritative for status, facts, evidence, provenance, proof, freshness, risk, uncertainty, and failure state.

## Evidence-quality boundary

The manifest preserves:

- Evidence Receipt schema `1`;
- Proof Score schema `1`;
- accepted proof-strength vocabulary;
- risk separate from proof;
- missing evidence remains unknown/unavailable rather than fabricated false/zero.

A Scout fails closed if these declarations are missing, malformed, or weakened.

## X1 normalized exact-mint identity — CMIS 1.11.0

The existing X1 `asset_lookup` service now publishes the bounded identity contract:

```text
identity_contract_version = x1_asset_identity/v1
exact_mint_normalization = true
normalized_identity_root = mint
metaplex_xdex_reconciliation = true
```

For syntactically valid exact X1 mint addresses, CMIS uses the accepted read-only Token Metadata provider and separately observes any exact-mint XDEX representation. The mint remains the canonical fungible identity root.

Metaplex `name`, `symbol`, and `uri` are on-chain descriptive metadata. XDEX `name` and `symbol` are provider-reported market representation. Agreement does not establish safety, legitimacy, ownership, or project truth.

Deterministic reconciliation states are:

- `metaplex_only` — verified on-chain metadata exists and XDEX has no exact-mint representation;
- `agreement` — the exact mint exists in both sources and comparable descriptors agree;
- `descriptor_conflict` — the exact mint is the same but comparable descriptors disagree; service state is partial and the mint is not changed;
- `xdex_unavailable` — Metaplex identity is verified but the XDEX provider/catalog could not be observed, so CMIS does not mislabel the mint as absent from XDEX;
- `metadata_unavailable` — accepted normalized on-chain descriptors are unavailable; any XDEX-only result remains explicitly partial/provider-scoped.

Symbol or name equality never reconciles different mints. URI contents are not verified merely because the URI string is stored on-chain. Metadata update authority/mutability remain separate from SPL mint/freeze authority.

## Phase 11 `intelligence_foundation`

Phase 11 established read-only Verified Intelligence primitives such as top-account concentration, neutral wallet activity, sanitized intelligence history, and evidence-bound conclusions.

The foundation itself remains non-promoted:

```text
read_only = true
public_service_promoted = false
scout_reliance_promoted = false
promotion_rule = new_accepted_public_service_contract_required
```

Foundation primitive names do not silently become public services.

## Phase 12 narrow promotion

CMIS `1.9.0` separately promotes exactly one wrapper service on X1:

```text
service = concentration_change_intelligence
service_contract = concentration_change_intelligence/v1
chain = x1
state = bounded
callable = true
read_only = true
public_service_promoted = true
scout_reliance_promoted = true
accepted_conclusion_type = top_account_concentration_change
promotion_scope = cmis_owned_top_account_concentration_change_evidence_by_id
execution_authorized = false
```

For this operation, Scouts require CMIS contract `>=1.9.0` and must validate the exact service contract, chain, state, callable/read-only flags, promotion flags, accepted conclusion type, promotion scope, and `execution_authorized=false` before dispatch.

Solana is explicitly classified for this service as unavailable, non-callable, non-promoted, and `execution_authorized=false`.

The promotion does not change the Phase 11 foundation-level non-promotion flags and does not promote wallet activity, generic history, raw concentration snapshots, behavioral labels, ownership inference, or other intelligence primitives.

## Historical comparison modes — CMIS 1.10.0

The existing public service name remains `historical_compare`. X1 adds deterministic mode selection without creating a new authority surface:

```text
mode = window
  -> existing metric + explicit 24h / 7d / 30d comparison

mode = all_available
  -> summarize every verified observation stored by CMIS for one asset,
     including bounded verified provider price backfill when available

mode = all_available_pair
  -> compare two assets only over their overlapping verified CMIS history
```

`all_available` is deliberately narrower than “complete asset lifetime.” The response exposes exact first/last verified observation times, observation counts, sampled min/max/change, sampled price drawdown, explicit observed gaps, and coverage limitations. It preserves:

```text
full_asset_lifetime_verified = false
continuous_coverage_verified = false
```

### CMIS 1.12.0 verified provider price backfill\n\nuntil separate evidence proves those stronger claims. X1 now permits a narrow provider-price backfill only when XDEX close observations are cross-checked against the matching X1.Ninja OHLCV pair and timestamp/interval scope, then stored with explicit provenance. The backfill is price-only; liquidity and volume are not imported. Provider source independence, archive completeness, continuous coverage, and historical USD-stable peg behavior remain unverified. Pair mode requires a second exact asset and aligned overlapping anchors within the explicit tolerance policy.

## Chain boundary

### X1

X1 is the mature CMIS surface. `pre_trade_check` remains bounded and analysis-only. Selected route-scoped price-impact or fee facts may be usable only when exact route/source/freshness/semantic/unit/proof requirements pass.

### Solana

Solana Phase 10 remains a bounded read-only provider/runtime foundation beneath the same CMIS contract. Exact-mint identity and bounded/partial market, tokenomics, risk, and narrow historical services are capability-specific. Recognition of the chain does not imply X1 parity or availability of the Phase 12 concentration service.

## Drift protection

The manifest is validated against runtime services and known-chain classifications. A new runtime service or chain must be explicitly classified rather than inheriting another chain's capabilities.

Scouts also fail closed on old, missing, malformed, incompatible, or unexpectedly promoted capability data.

The live `/v1/cmis/capabilities` response is authoritative for deployed eligibility, but deployed state must still satisfy the accepted Scout contract before use.

## Safety boundary

This capability contract authorizes no transaction construction, simulation as an execution precursor, signing, broadcasting, custody, swap execution, autonomous trading, bridge transfer, or autonomous value movement.
