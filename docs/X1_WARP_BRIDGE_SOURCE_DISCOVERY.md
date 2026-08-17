# X1 Warp Bridge source discovery

Research date: **2026-08-17**

Refresh note: this discovery boundary is carried forward onto the current accepted CMIS `main`. It does not promote any bridge host, endpoint, UI label, asset representation, fee, capacity, guardian state, or transfer state into CMIS truth.

## Purpose

Identify the machine-readable source behind the official X1 Warp Bridge without treating UI labels or third-party discovery clues as CMIS-authoritative bridge facts.

This is a discovery record, not a bridge-health or capacity report.

## Verified official UI surface

The official bridge application exposes these user-facing routes:

- `https://app.bridge.x1.xyz/` — bridge route / transfer UI;
- `https://app.bridge.x1.xyz/history` — wallet-scoped transaction history UI;
- `https://app.bridge.x1.xyz/info` — described by the official UI as real-time bridge status and configuration.

The public server-rendered/search-visible pages establish that structured bridge concepts exist in the application. They do **not** identify the underlying API, on-chain account, cache, RPC method, or indexer used to supply those values.

Do not promote a displayed `Offline`, `Checking`, fee, capacity, guardian, or token status label as a current CMIS fact from this discovery record.

## Candidate API-host lead — unverified

A third-party Chrome-extension metadata index reports that an X1 Wallet version added host permissions for:

- `https://bridge-api.x1.xyz/*`;
- `https://app.bridge.x1.xyz/*`.

This is **non-authoritative discovery evidence only**. The current search pass did not find an X1-owned public API document or indexed endpoint contract for `bridge-api.x1.xyz`.

Therefore:

```text
bridge-api.x1.xyz
classification = UNVERIFIED CANDIDATE HOST
CMIS source status = NOT ACCEPTED
```

Do not hard-code or production-call guessed paths under this hostname until an X1-owned source, application-network observation, or deterministic safe probe establishes the actual contract.

## What must be discovered

The bridge UI implies several distinct data contracts that should remain separate in CMIS:

### 1. Operational state

Needed fields:

- source and destination chain identity;
- service/route state;
- observed-at / source timestamp;
- stale/degraded state;
- provider/source provenance.

### 2. Supported asset / representation registry

Needed fields:

- canonical asset identity;
- Solana representation mint/address;
- X1 representation mint/address;
- direction support;
- decimals;
- bridge route identifier;
- enabled/disabled status with timestamp.

### 3. Capacity / limits

Needed fields:

- route and asset;
- capacity/limit value;
- units;
- window semantics;
- reset time;
- currently used / remaining capacity where exposed;
- source timestamp.

### 4. Fee model

Needed fields:

- bridge fee;
- network fee / estimate;
- source and destination fee denomination;
- quote timestamp;
- fixed vs estimated semantics.

### 5. Guardian / signer state

Needed fields:

- guardian/signer identity;
- public key/address;
- chain/role;
- quorum/threshold semantics;
- active/inactive state;
- freshness;
- configuration version/epoch if available.

### 6. Transfer lifecycle / history

Needed fields:

- transfer identifier;
- source transaction signature;
- destination transaction signature;
- source/destination chain;
- canonical asset + representations;
- raw amount + decimals;
- created/updated timestamps;
- lifecycle state;
- source/destination finality;
- failure/refund/retry semantics.

Wallet-scoped UI history does not by itself establish a public global-history API.

## Safe discovery sequence

1. Inspect official application network requests or delivered application assets to identify exact host/path contracts.
2. Record whether each source is HTTP, RPC, WebSocket/SSE, embedded configuration, or direct on-chain reads.
3. For each discovered read endpoint, perform an explicit **GET/read-only** contract probe first.
4. Record HTTP status, content type, required authentication, headers/rate limits, schema, timestamp behavior, and deterministic failures.
5. Do not send bridge-transfer POST requests, wallet signatures, approvals, or value-moving transactions for source discovery.
6. If a field originates from an on-chain account, create a chain-specific parser and retain account/slot provenance instead of depending on the UI cache.
7. Keep bridge operational state, configuration, capacity, guardians, and transfer history as separate evidence types even if one API returns them together.

## Acceptance rule for `bridge-api.x1.xyz`

The candidate host may enter the X1 Provider only after at least one of these establishes provenance:

- X1-owned documentation naming the host/endpoint;
- direct observation that the official `app.bridge.x1.xyz` application requests that endpoint;
- an X1-owned application/configuration artifact naming it;
- an independently verifiable on-chain configuration pointing to the service.

Then CMIS must contract-test individual paths. Host provenance alone is not endpoint-semantic proof.

## Current conclusion

The official Warp Bridge clearly has structured bridge state/configuration/history concepts, but this research pass still does **not** establish a stable public read-only machine API contract.

The candidate hostname `bridge-api.x1.xyz` is worth direct application-network inspection, but remains unverified and must not be treated as current bridge truth.

Next engineering action: capture the official bridge application's read-only network calls (without connecting/signing a wallet where not required), then implement narrowly scoped contract probes for the exact observed endpoints.

## Research sources

Official X1 bridge UI:

- `https://app.bridge.x1.xyz/`
- `https://app.bridge.x1.xyz/history`
- `https://app.bridge.x1.xyz/info`

Non-authoritative discovery lead only:

- Chrome extension metadata index for the X1 Wallet, which reports historical host permissions including `bridge-api.x1.xyz`.
