# Scout ↔ CMIS Capability Contract

Last reconciled: 2026-08-20

CMIS publishes machine-readable service eligibility at:

```text
GET /v1/cmis/capabilities
```

This endpoint belongs to the **Chain Scout ↔ CMIS** boundary. Roberta does not call providers directly and does not perform provider-specific capability discovery.

## Contract identity

Accepted baseline:

- capability schema: `1`
- global existing-service minimum: `1.8.0`
- current CMIS contract: `1.9.0`
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

## Post-Phase-12 internal deterministic foundations

CMIS now also contains accepted deterministic classification and wallet-relationship evidence contracts. They remain internal implementation foundations and do **not** add runtime public services or change the capability manifest.

The wallet-relationship foundation records only observed direct verified-transfer relationships reconstructed from canonical CMIS wallet-activity evidence. It does not establish ownership, beneficial ownership, behavior, intent, risk, complete history, or complete graph coverage.

For both later internal foundations:

```text
public_service_promoted = false
scout_reliance_promoted = false
cmis_promotable = false
execution_authorized = false
```

Issue #255 therefore required no CMIS capability-contract version bump and grants no new Scout dispatch authority.

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
