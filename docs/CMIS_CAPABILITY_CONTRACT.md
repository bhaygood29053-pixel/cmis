# Scout ↔ CMIS Capability Contract

CMIS publishes a machine-readable service-eligibility contract for Chain Scouts at:

```text
GET /v1/cmis/capabilities
```

This endpoint belongs to the **Chain Scout ↔ CMIS** boundary. Roberta does not call it directly and does not need provider-specific knowledge.

## Contract identity

The current contract is:

- capability schema: `1`
- CMIS contract: `1.6.0`
- request path: `/v1/cmis`

The original flat `version`, `supported_services`, `supported_chains`, and `known_chains` fields remain for backward compatibility. New Scout integrations must use `chains.<chain>.services.<service>` when deciding whether a CMIS operation is eligible.

## Capability states

Each known chain classifies every runtime-advertised service as one of:

- `supported` — callable and accepted as a normal service surface;
- `bounded` — callable only within explicit requirements/limitations;
- `partial` — callable, but the service is intentionally incomplete and must preserve unavailable/unverified fields;
- `unavailable` — not callable for that chain; callers must not infer or route around the boundary.

Each record also carries:

- `callable`
- `requirements`
- `limitations`

A capability state describes **service eligibility**, not provider health or a guarantee that an individual request will return `ok`. Normal CMIS responses remain authoritative for request-time status, evidence, provenance, confidence, and failures.

## Drift protection

The capability manifest is validated against the runtime service list and known-chain list when the HTTP module is loaded. If a developer adds a new runtime service or known chain without explicitly classifying it for every known chain, CMIS fails loudly instead of silently advertising an ambiguous interface.

This means future Ethereum work must first add an explicit Ethereum capability table before the chain can become part of the accepted CMIS runtime contract.

## Current high-level chain boundary

X1 has the mature service surface. `pre_trade_check` remains bounded and analysis-only; execution authorization remains false and slippage, price impact, route quality, fees, and transaction simulation remain unavailable until verified producers exist.

Solana is intentionally narrower. Exact-mint identity, market/tokenomics/risk, and the narrow historical slice can be callable under their documented requirements. Ranking, pre-trade, trade verification, verified asset activity, and persisted verification-evidence lookup remain unavailable until separately implemented and promoted.

## Rollout order

Deploy the CMIS capability contract before enabling a Scout build that requires contract version `1.6.0`. A newer Scout encountering an old, missing, malformed, or incompatible capability contract must fail closed rather than sending an assumed-supported service request.

No signing, broadcasting, wallet custody, transaction construction, or execution authority is introduced by this contract.
