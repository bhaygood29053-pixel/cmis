# Scout ↔ CMIS Capability Contract

Last reconciled: 2026-08-28

CMIS publishes machine-readable service eligibility at:

```text
GET /v1/cmis/capabilities
```

This endpoint belongs to the **Chain Scout ↔ CMIS** boundary. Roberta does not call providers directly and does not perform provider-specific capability discovery.

## Contract identity

Accepted baseline:

- capability schema: `1`
- global existing-service minimum: `1.8.0`
- current CMIS contract: `1.21.0`
- request path: `/v1/cmis`
- Evidence Receipt schema: `1`
- Proof Score schema: `1`
- intelligence-foundation schema: `1`
- intelligence-evidence schema: `1`

The flat `version`, `supported_services`, `supported_chains`, and `known_chains` fields remain compatibility metadata. Service eligibility is determined from validated per-chain service records plus the evidence-quality and intelligence-foundation declarations.

## Public service capability states

Each known chain classifies each runtime-advertised public service as `supported`, `bounded`, `partial`, or `unavailable`, with explicit `callable`, `requirements`, and `limitations` fields.

A capability state describes service eligibility, not provider health and not a guarantee that an individual request returns `ok`. Request-time CMIS responses remain authoritative for status, facts, evidence, provenance, proof, freshness, risk, uncertainty, and failure state.

## Universal response freshness — CMIS 1.27

Every public CMIS service response includes top-level `freshness` using `cmis_response_freshness/v1`. This is an additive response-envelope invariant, including token requests that fail, resolve ambiguously, or lack service-specific fact-time proof.

The common envelope never treats `observed_at` or collection time alone as provider-fact freshness. When a service supplies accepted freshness evidence, it is preserved under `freshness.details` and may promote `freshness.state`. When service-specific freshness evidence is absent, the response fails closed to `UNKNOWN` with `freshness_verified=null` rather than omitting freshness.

## Evidence-quality boundary

The manifest preserves:

- Evidence Receipt schema `1`;
- Proof Score schema `1`;
- accepted proof-strength vocabulary;
- risk separate from proof;
- missing evidence remains unknown/unavailable rather than fabricated false/zero.

A Scout fails closed if these declarations are missing, malformed, or weakened.

## Instant X1 Scan — CMIS 1.14.0

CMIS 1.14.0 promotes the bounded X1-only composition service to:

```text
service = instant_x1_scan
service_contract_version = instant_x1_scan/v2
chain = x1
read_only = true
public_service_promoted = true
scout_reliance_promoted = true
execution_authorized = false
```

The service composes accepted CMIS outputs for exact identity, current market, tokenomics, verified historical observations, deterministic risk, and runtime evidence-quality metadata. It does not introduce a new truth authority.

Instant X1 Scan v2 may invoke the already accepted bounded XDEX/X1.Ninja price-history backfill before constructing the all-available history section. Imported observations are cross-corroborated under the existing provider-price contract and remain price-only. The scan exposes exact verified observation bounds, observation counts, gap diagnostics, and provider-backfill metadata.

Provider range/archive completeness, source independence, complete asset lifetime, and continuous historical coverage remain unverified unless separate deterministic proof gates establish them. v2 must not turn a longer bounded series into a lifetime or continuity claim.

The scan intentionally does not expand X1 RPC mint-address coverage. Omitted on-chain coverage is represented as `not_requested`, not as a missing-provider error. This distinction does not weaken ordinary `historical_compare` coverage semantics.

Holder-looking provider values remain unverified unless the existing holder semantic/coverage contract passes. Current top-account concentration is explicitly unavailable in `instant_x1_scan/v2`; internal intelligence foundations are not used as a public shortcut.

The runtime EvidenceQualityMixin attaches the scan Evidence Receipt and Proof Score after the deterministic service result is complete. Proof Score remains separate from risk and cannot rewrite facts, scan status, or authority.

Solana advertises `instant_x1_scan` as unavailable. Solana product expansion and release remain deferred to a future phase.

## X1 Burn Intelligence — CMIS 1.15.0

CMIS 1.15.0 promotes the accepted X1 burn foundation as its own public service:

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

The service reuses the accepted tokenomics/burn-scanner path and does **not** create a second parser or recalculate burn facts. Exact mint is the identity root.

The contract exposes the accepted cumulative verified-observed burn facts plus the exact 1h, 24h, 7d, and 30d windows. The 24h/7d/30d windows preserve their immediately preceding equal-length comparison periods and CMIS-owned percentage-change state. Undefined zero-denominator comparisons remain null with explicit state rather than infinity.

`verified_burned_observed` is bounded to proven scanned/verified coverage. It is not a lifetime-total claim unless `lifetime_total_burn_verified=true`. Dead-address transfers are not burns without separately accepted burn semantics.

Mint/emission facts, burn-to-emission ratio, net issuance, circulating-supply context, and historical value destroyed remain available only under their existing independent verification gates. Missing or incomplete evidence remains unavailable/partial.

Runtime Evidence Receipt and Proof Score post-processing may bind the final Burn Intelligence response, but Proof Score remains separate from risk and cannot rewrite burn facts, status, completeness, or execution policy.

Solana advertises `burn_intelligence` as unavailable/non-callable/non-promoted in v1.

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


## Bridge-to-XDEX Utilization — CMIS 1.19.0

Issue #482 promotes the already accepted `bridge_to_xdex_utilization/v1`
contract for X1 as a bounded read-only public service and authorizes X1 Scout
reliance on that exact CMIS result.

```text
service = bridge_to_xdex_utilization
service_contract_version = bridge_to_xdex_utilization/v1
chain = x1
state = bounded
callable = true
read_only = true
public_service_promoted = true
scout_reliance_promoted = true
execution_authorized = false
```

The public response accepts only a CMIS-owned canonical #410 record resolved
inside the protected runtime. It revalidates the content hash, exact route,
source/destination mints, verified XDEX program-family scope, 24h coverage,
USD-unit compatibility, fact-time freshness, comparable value basis, and
non-promotion guardrails.

This promotion does not make the verified XDEX program family every X1 DEX.
A bounded zero wSOL.X result is not a global zero. Bridge activity is not
adoption. Liquidity is not volume. No causal inference or automatic risk
conclusion is authorized. Global on-chain DEX discovery and recognized-program
registry exhaustiveness remain false; source independence remains false unless
separately proven.


## Instant X1 Scan v4 — CMIS 1.21.0

CMIS 1.21 promotes `instant_x1_scan/v4` as the bounded X1 composition for
`x1_current_market_freshness/v2`. v3 remains unchanged and backward
compatible.

v4 may surface field-scoped rolling 24h volume and transaction freshness only
from accepted exact rolling-window evidence. It does not convert provider
collection time into provider fact time, does not establish source
independence, and does not authorize execution.

## Cross-Chain Asset Provenance — CMIS 1.20.0

Issue #491 promotes the accepted `cross_chain_asset_provenance/v1` foundation
through a bounded X1-only public service.

```text
service = cross_chain_asset_provenance
service_contract_version = cross_chain_asset_provenance/v1
chain = x1
state = bounded
callable = true
read_only = true
public_service_promoted = true
scout_reliance_promoted = true
execution_authorized = false
```

The protected runtime owns the canonical provenance resolver. Scout callers may
select a CMIS-owned content-addressed record and bind it to an exact current X1
asset id/kind, but may not submit or reconstruct lineage, representation depth,
bridge/custody dependencies, or verification claims.

The service proves structural identity continuity only. It does not prove live
bridge state, backing, solvency, safety, custody truth, adoption, causality,
source independence, or risk. Symbol/name equality never establishes identity.

## CMIS 1.26 regulatory evidence promotion

Issue #539 promotes the accepted `regulatory_evidence/v1` foundation as a
bounded X1-only read service.

```text
service = regulatory_evidence
service_contract_version = regulatory_evidence/v1
chain = x1
state = bounded
callable = true
read_only = true
public_service_promoted = true
scout_reliance_promoted = true
compliance_conclusion_authorized = false
execution_authorized = false
```

Promotion requires exact X1 mint binding, primary-law provenance,
freshness-sensitive primary-regulator provenance, explicit current rulemaking
status, and bounded evidence age. Proposed rules cannot be promoted as final or
effective regulations. The service does not determine legal compliance, provide
legal advice, infer risk, or authorize execution.

Solana remains unavailable/non-callable/non-promoted for this service.
