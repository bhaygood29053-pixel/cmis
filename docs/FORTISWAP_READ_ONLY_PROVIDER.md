# FortiSwap read-only provider qualification

Issue: #413

## Purpose

FortiSwap is a third-party X1 router/execution provider that exposes a machine-readable x402 catalogue and X1 token/quote/router data. CMIS may use it as an observational evidence source, but FortiSwap is not a CMIS authority.

Official machine discovery:

- `https://app.fortiblox.com/api/x402/discovery`
- `https://app.fortiblox.com/llms.txt`

Officially documented priced routes at qualification time:

- `GET /api/tokens`
- `GET /api/token/{mint}`
- `GET /api/router/volume`
- `POST /api/quote`
- `POST /api/tx/build`

CMIS qualifies only the first four as read-only observation surfaces. The implementation normalizes already-obtained paid responses but does not implement x402 payment or API-key handling.

## Authority boundary

FortiSwap fields including `trust`, `confidence`, `safety`, `highImpact`, `thinLiquidity`, and `warnings` are provider assertions.

They do not by themselves establish:

- CMIS verification;
- Proof Score;
- deterministic CMIS risk;
- source independence;
- bridge truth;
- execution authorization.

Where an equivalent XDEX/RPC fact exists, future CMIS reconciliation must compare the FortiSwap observation against accepted independent evidence and preserve disagreement.

## Discovery fingerprint

The provider module hashes:

1. the complete discovery catalogue;
2. each discovery item;
3. the method/route/schema subset for each item.

A newly discovered route is retained as evidence but remains `unqualified` until explicitly accepted. Discovery cannot silently expand CMIS authority.

## Explicit execution block

The following remain blocked by policy:

- `POST /api/tx/build`;
- `POST /api/tx/send`;
- `POST /api/tx/status`;
- wallet keys;
- signing;
- broadcast;
- swaps;
- custody;
- bridge value movement.

Every normalized FortiSwap record preserves:

```text
analysis_only = true
execution_authorized = false
```

Quote normalization additionally preserves:

```text
transaction_build_allowed = false
cmis_verified = false
cmis_risk_promoted = false
```

## Bridge limitation

FortiSwap's web application exposes a bridge product, but the machine catalogue documented at qualification time does not publish a bridge quote/status semantic contract.

Therefore FortiSwap does not unblock Warp Issue #407, bridge-flow Issue #409, or bridge-to-XDEX utilization Issue #410. Any future FortiSwap bridge endpoint requires a separate exact semantic qualification gate before CMIS may treat it as bridge evidence.

## Deterministic CI

Ordinary tests use static provider-shaped fixtures and an injected discovery transport. They make no paid x402 call, require no wallet, and move no value.
