# Scout ↔ CMIS Capability Contract

CMIS publishes a machine-readable service-eligibility contract for Chain Scouts at:

```text
GET /v1/cmis/capabilities
```

This endpoint belongs to the **Chain Scout ↔ CMIS** boundary. Roberta does not call it directly and does not need provider-specific knowledge.

## Contract identity

The accepted contract is:

- capability schema: `1`
- minimum current CMIS contract: `1.8.0`
- request path: `/v1/cmis`
- Evidence Receipt schema: `1`
- Proof Score schema: `1`
- intelligence-foundation schema: `1`
- intelligence-evidence schema: `1`

The flat `version`, `supported_services`, `supported_chains`, and `known_chains` fields remain compatibility metadata. Chain Scouts decide service eligibility from the validated chain/service records and must also enforce the accepted evidence-quality and intelligence-foundation boundary.

## Public service capability states

Each known chain classifies every runtime-advertised public service as one of:

- `supported` — callable as an accepted normal service surface;
- `bounded` — callable only within explicit requirements/limitations;
- `partial` — callable but intentionally incomplete, with unavailable/unverified fields preserved;
- `unavailable` — not callable for that chain; callers must not infer or route around the boundary.

Each service record also carries:

- `callable`;
- `requirements`;
- `limitations`.

A capability state describes **service eligibility**, not provider health and not a guarantee that an individual request returns `ok`. Request-time CMIS responses remain authoritative for status, evidence, provenance, proof, freshness, uncertainty, and failures.

## Evidence-quality boundary

Contract `1.8.0` requires the manifest to advertise the accepted Evidence Receipt / Proof Score rules, including:

- Evidence Receipt schema `1`;
- Proof Score schema `1`;
- accepted proof-strength vocabulary;
- risk remains separate from proof;
- missing evidence remains unknown rather than becoming a fabricated false/zero value.

A Chain Scout that requires this contract must fail closed if these evidence-quality declarations are missing, malformed, or weakened.

## Phase 11 `intelligence_foundation`

CMIS `1.8.0` also advertises the read-only Phase 11 Verified Intelligence foundation.

Accepted primitive names are:

- `top_account_concentration`;
- `wallet_activity_facts`;
- `sanitized_intelligence_history`;
- `evidence_bound_conclusions`.

The foundation is deliberately **not** a public service surface. The manifest must preserve:

```text
read_only = true
public_service_promoted = false
scout_reliance_promoted = false
promotion_rule = new_accepted_public_service_contract_required
```

Every individual intelligence-foundation record must remain bounded/read-only and unpromoted. These primitive names must not silently appear in `supported_services`.

Post-foundation deterministic helpers, such as explicit-policy concentration-threshold evaluation, do not become public Scout services merely because they exist inside CMIS.

## Current high-level chain boundary

### X1

X1 has the mature service surface. `pre_trade_check` remains bounded and analysis-only.

Recent XDEX evidence permits selected exact-route pre-trade facts to become usable **internally** when strict route identity, source, freshness, semantic, unit, and accepted proof-basis gates pass. This does not make route evidence caller-supplied through the public HTTP gateway and does not authorize execution.

Current distinctions include:

- route-scoped price impact may be usable when independently verified;
- bounded 0.28% AMM/execution-model fee evidence may be usable for an exact accepted route/evidence scope;
- XDEX quote slippage tolerance is not expected execution slippage;
- expected execution slippage, route quality, fill quality, transaction simulation, and generic execution quality remain unavailable unless separately proven.

### Solana

The Phase 10 Solana read-only provider/runtime foundation is implemented beneath the same CMIS architecture.

Depending on the deployed manifest and configured providers, exact-mint identity and bounded/partial market, tokenomics, risk, and narrow historical services may be callable. Ranking, Solana pre-trade execution modeling, trade verification, verified asset-wide activity, signing, broadcasting, and custody remain unavailable until separately implemented and promoted.

Service availability is capability-specific; a chain being recognized does not imply parity with X1.

## Drift protection

The capability manifest is validated against the runtime service list and known-chain list. A new runtime service or known chain requires explicit classification rather than silently inheriting another chain's capabilities.

A future Ethereum foundation must therefore begin with an explicit Ethereum capability table and acceptance contract.

Scouts also validate the manifest. An old, missing, malformed, promoted, or incompatible capability contract fails closed before service dispatch.

## Safety boundary

This capability contract adds no:

- transaction construction;
- signing;
- broadcasting;
- wallet custody;
- swap execution;
- autonomous trading;
- bridge transfer;
- autonomous value movement.

The live `/v1/cmis/capabilities` response is authoritative over documentation when determining what a deployed CMIS instance can currently serve.
