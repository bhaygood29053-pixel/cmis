# FortiBlox X1 provider source discovery

Research date: **2026-08-18**

## Purpose

Evaluate FortiBlox only as a possible third-party X1 Provider source for read-only chain/indexer/RPC evidence.

This record does **not** promote FortiBlox into CMIS and does not certify any current FortiBlox metric, endpoint uptime, source independence, historical completeness, or real-time semantics.

## Current classification

```text
source = FortiBlox
role = candidate third-party X1 explorer/indexer/RPC source
provider_status = CANDIDATE
explorer_rest_api_documented = true
explorer_exact_endpoint_list_verified = false
nexus_rpc_contract_verified = false
public_api_implementation_repo_found = false
source_independence_verified = false
history_completeness_verified = false
freshness_verified = false
cmis_promotable = false
```

## 1. FortiBlox Explorer — current documented REST API claim

Current FortiBlox Explorer documentation states that Explorer data is available programmatically through a REST API and that endpoints return JSON. The docs describe coverage for:

- network / epoch / TPS / recent blocks / transactions;
- accounts, balances, token holdings, and transaction history;
- validators, rewards, and delegations;
- NFTs and DeFi;
- XDEX market data.

The same current documentation says the full endpoint list is exposed through interactive API docs inside the Explorer.

Source:

- `https://docs.fortiblox.com/docs/explorer/api-access`

### Current contract-discovery result

The documentation's current interactive API-docs link resolves to:

- `https://docs.fortiblox.com/api-docs`

During this research pass, that URL returned **HTTP 404 Not Found**.

Therefore the public documentation establishes a provider-owned claim that a JSON REST API exists, but it does **not** currently provide CMIS with a stable exact endpoint list or response schema through the linked contract surface.

Accepted interpretation:

```text
Explorer REST capability claim = DOCUMENTED
exact REST endpoint contract = UNAVAILABLE / NOT VERIFIED
production adapter eligibility = false
```

Do not guess endpoint paths from Explorer UI routes.

## 2. Explorer provenance claim

Current Explorer documentation states that Explorer values are sourced from the X1 blockchain and that unavailable/unpriced values should be represented explicitly rather than invented.

Source:

- `https://docs.fortiblox.com/docs/explorer/intro`

This is useful provider-owned provenance language, but it does **not** prove:

- which RPC/node/indexer infrastructure supplies each field;
- whether FortiBlox observations are independent from the official X1 RPC path used elsewhere by CMIS;
- historical retention depth;
- finality/commitment semantics;
- continuous coverage;
- indexer lag/freshness;
- exact XDEX market-data provenance;
- same-fact independence for CMIS corroboration.

A different provider/domain is not sufficient evidence of source independence.

## 3. FortiBlox Nexus RPC — named but lifecycle status is ambiguous

FortiBlox's RPC Proxy documentation contains examples that forward Solana-compatible JSON-RPC payloads to an exact upstream URL shaped as:

```text
https://nexus.fortiblox.com/rpc?api-key=<API_KEY>
```

Source:

- `https://docs.fortiblox.com/docs/nexus/security/rpc-proxy`

The same documentation page contains conflicting lifecycle signals:

- the page labels the RPC proxy as under development / `Coming Q1 2025`;
- later roadmap material on the same page marks some proxy functionality as completed;
- examples include read methods such as `getSlot` / `getHealth` and also transaction-send examples.

Because the current public contract state is internally inconsistent, CMIS must not infer that the named Nexus RPC endpoint is currently production-accessible, supported for X1 history, or suitable for promotion.

Accepted interpretation:

```text
nexus RPC hostname/path provenance = PROVIDER-NAMED SUPPORTING EVIDENCE
current access = UNVERIFIED
method coverage = UNVERIFIED
archive/history retention = UNVERIFIED
source independence = UNVERIFIED
CMIS promotion = false
```

No credential-bearing live probe was performed in this discovery pass.

## 4. Public implementation-repository check

The FortiBlox documentation links to the provider's public GitHub organization:

- `https://github.com/fortiblox`

At this research observation, that organization exposed six public repositories: `X1-Forge`, `X1-Aether`, `X1-Stratus`, `x1-nimbus`, `Listenarr`, and `fortiblox-router`.

No public repository for the Explorer REST API, Nexus RPC service, or the documentation-referenced `fortiblox-rpc-proxy` implementation was present in that visible repository set.

The RPC Proxy documentation itself describes `github.com/fortiblox/fortiblox-rpc-proxy` as a future/coming-soon repository. That documentation reference is therefore not accepted as proof that an implementation repository currently exists.

Accepted interpretation:

```text
provider GitHub organization provenance = VERIFIED PUBLIC SURFACE
public Explorer API implementation repo = NOT FOUND
public Nexus RPC implementation repo = NOT FOUND
public fortiblox-rpc-proxy repo = NOT FOUND IN CURRENT PUBLIC REPO SET
implementation contract inferred from docs = forbidden
```

Absence of a public implementation repository does not prove the services do not exist. It only means CMIS cannot use public source code to close the contract/provenance gap in this pass.

## 5. Why FortiBlox may still be useful

FortiBlox remains worth investigating because its public Explorer is X1-specific and exposes account/block/transaction/validator/token surfaces that could potentially provide:

- a secondary transaction/indexer observation;
- bounded account/token observations;
- historical transaction lookup;
- validator/network evidence;
- an independent UI/indexer comparison when actual upstream independence is proven.

These are candidate roles only.

## 6. Required verification before any adapter

Before FortiBlox enters the X1 Provider, CMIS requires an exact read-only contract for each promoted capability.

### Explorer REST API

1. Obtain the current exact provider-owned API base URL and endpoint list.
2. Record authentication requirements and quotas.
3. Contract-test one narrow endpoint at a time.
4. Verify response identity, units, pagination/range semantics, timestamps, stale behavior, and deterministic errors.
5. Prove the data subject is the exact requested X1 account/token/block/transaction.
6. Preserve raw-source provenance without promoting UI labels into chain truth.

### Nexus RPC

1. Confirm the exact current X1 RPC URL and authentication contract from current provider-owned documentation or support material.
2. Begin with read-only methods only (`getHealth`, `getSlot`, then explicit historical reads if supported).
3. Do not send transaction/write methods during source verification.
4. Verify actual provider/source independence before using results as corroboration.
5. Verify retention depth and requested-slot behavior before any archival claim.
6. Verify commitment/finality semantics and error handling.
7. Keep sparse observations non-promotional.

## 7. Fail-closed rules

FortiBlox must remain non-promotional if any of the following is unresolved:

- exact endpoint contract;
- authentication contract;
- subject identity;
- units/decimals;
- pagination or history range;
- freshness/observation time;
- source independence;
- retention/finality semantics;
- malformed or undocumented success envelopes.

Missing values must remain unavailable rather than becoming zero.

## Safety

Read-only research only.

This work does not add:

- wallet custody;
- signer/key material;
- transaction preparation;
- transaction signing;
- transaction broadcasting;
- trading;
- bridge transfer;
- autonomous execution;
- value movement.

## CMIS conclusion

FortiBlox has a stronger current public evidence surface than a generic UI-only candidate: current provider-owned documentation explicitly claims an Explorer JSON REST API and describes its coverage.

However, the current linked interactive API contract is unavailable (404), the separately documented Nexus RPC surface has internally inconsistent lifecycle/status language, and no matching public API/RPC implementation repository was found in the provider's current public GitHub repository set.

Therefore:

```text
X1-ALT-02 = CANDIDATE
FortiBlox Explorer REST claim = documented
exact Explorer REST contract = unavailable
FortiBlox Nexus RPC = unverified supporting evidence
public implementation contract = unavailable
source independence = unverified
CMIS promotion = false
```

Next valid engineering step: obtain a current exact provider-owned Explorer API contract or exact Nexus RPC access contract, then add a narrowly scoped deterministic read-only classifier before any live/provider promotion.
