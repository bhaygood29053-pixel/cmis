# XONE → XNT Primary Allocation Artifact Resolution v1

Status: **ACCEPTED INTERNAL FOUNDATION** via Issue #622 / PR #623. Dedicated resolver run #3 passed deterministic and NO_LEAD operational jobs at head `21be1b27f10ffd1be4ab5d91ec6b1554b60f64c9`; Liquidity Scout Tests #1838 passed; PR #623 merged as `e288ed4bf4620654f64b57615a963efbe64e7700`.

Contract:

`xone_xnt_primary_allocation_artifact_resolution/v1`

## Purpose

The accepted XONE/XNT evidence track has exhausted the useful broad public discovery classes without finding a qualifying XONE allocation source.

Accepted `xone_xnt_allocation_source_provenance/v1` run #6 covered:

- 3/3 bounded repositories;
- 41 provenance-shaped repository files;
- 3/3 release queries;
- 3/3 official X1 targets;
- 10 clean X1 program/Anchor/IDL/PDA/account-schema architecture analogues;
- 0 qualifying XONE allocation-source candidates;
- 0 exact-XONE-bound allocation sources.

This contract does **not** launch another broad search.

Instead, it gives CMIS a deterministic resolver for the moment a concrete primary lead appears.

## Accepted lead shape

A lead is already-retrieved evidence supplied by a bounded caller.

Required fields:

- `source_id`
- `source_role`
- exact HTTPS `url`
- non-empty artifact `text`
- numeric `observed_at`

Optional fields:

- repository/file `path`
- pinned `revision`
- `release_name`
- `content_type`
- independent `expected_sha256`
- `release_asset`
- `architecture_analogue`

The resolver performs **zero network discovery**.

It does not fetch arbitrary URLs, search GitHub, scrape websites, query RPC, enumerate accounts, or discover adjacent sources.

## Exact XONE identity

Accepted Ethereum XONE contract:

`0x4DCDa2274899d9BbA3Bb6f5A852C107Dd6E4fE1c`

Resolution preserves:

- XONE name-only context;
- XONE semantic allocation context;
- exact accepted-contract binding;
- architecture-analogue status.

Name-only XONE is not exact source binding.

## Resolution states

### `NO_LEAD`

No explicit artifact was supplied.

This is a valid PASS state.

Required properties:

`network_discovery_performed=false`
`network_request_count=0`
`lead_supplied=false`
`primary_artifact_candidate_discovered=false`
`primary_artifact_resolved_for_handoff=false`

### `REJECTED`

The supplied lead is not a concrete allocation-source artifact under the accepted provenance contract.

Examples:

- ordinary ABI;
- generic config;
- invalid HTTP/non-HTTPS locator;
- expected SHA-256 mismatch;
- MoonParty used as substitute evidence without an exact XONE allocation source;
- generic airdrop/program material that does not qualify even as a bounded analogue.

### `CANDIDATE`

The artifact is provenance-shaped but is not yet eligible for an exact downstream handoff.

Common reasons:

- XONE name-only rather than accepted-contract binding;
- architecture analogue;
- mutable/unpinned locator;
- incomplete provenance.

Candidate handoffs may be preserved for review, but are not authorized.

### `RESOLVED_FOR_HANDOFF`

A lead reaches this state only when all are true:

1. concrete allocation-source provenance exists;
2. XONE allocation semantics are present;
3. the exact accepted Ethereum XONE contract is bound;
4. the source is not architecture-analogue-only;
5. provenance locator fields are complete;
6. the locator is pinned by revision/release or content addressing;
7. at least one downstream verification route exists.

This state means only:

> CMIS has a reproducible exact-XONE artifact ready for a stronger verifier.

It does not mean the allocation is authoritative or correct.

## Content integrity

CMIS always computes:

`artifact_sha256`

If `expected_sha256` is supplied, it must exactly match the retrieved artifact text or resolution fails closed.

Separate fields preserve:

- local content addressing;
- whether an independent expected hash was supplied;
- whether that expected hash matched.

A locally computed hash alone does not prove external publication integrity.

## Handoff routing

Resolved exact-XONE artifacts may route into stronger contracts.

### Structured holder/export or registry

`xone_xnt_x1_allocation_record_discovery/v1`

This may discover exact holder/allocation rows, but does not verify eligibility or issuance.

### Explicit snapshot block

`ethereum_xone_snapshot_registry/v1`

This can trigger the already-accepted full Ethereum XONE holder-ledger reconstruction and two-RPC registry digest proof.

### Merkle artifact

`xone_xnt_snapshot_allocation_binding_verification/future`

A Merkle root/tree/proof still requires exact eligibility/formula/leaf semantics before promotion.

### X1 program/account schema

`xone_xnt_x1_program_account_qualification/future`

Direct finalized X1 RPC qualification becomes eligible only for the exact discovered program/account schema.

### Allocation API

`xone_xnt_allocation_api_source_verification/future`

The exact endpoint/source must be separately verified.

### Content-addressed artifact

`xone_xnt_content_addressed_artifact_verification/future`

IPFS/Arweave resolution must independently retrieve and hash the immutable artifact.

### Release asset

`xone_xnt_release_asset_resolution/future`

Release provenance must be independently verified.

No handoff is executed by this resolver.

## Snapshot block handling

The resolver preserves explicit candidate block numbers only when the artifact text uses bounded snapshot/block language such as:

- `snapshot block 18650000`
- `snapshot at block 18650000`
- `block number: 18650000`

A number appearing elsewhere is not automatically a snapshot block.

## False-positive boundaries

Permanent boundaries include the accepted prior regressions plus:

- ordinary ABI does not become primary allocation evidence;
- generic config does not qualify without exact XONE binding;
- source IDs do not contribute evidence semantics;
- generic RPC/API URLs are not allocation APIs;
- arbitrary Base58 strings are not X1 program evidence;
- generic `export` language is not a registry export;
- `pda` must be a delimited path/schema concept, not a substring;
- IDL JSON is program schema, not automatically a holder file;
- MoonParty remains historical/non-priority and cannot substitute for the XONE snapshot/allocation source.

## No-lead operational runner

Operator:

`scripts/resolve_xone_xnt_primary_allocation_artifact.py`

With no `--lead-json`, it emits `NO_LEAD`.

With `--lead-json`, it resolves exactly one local artifact object.

The script intentionally imports no HTTP/network client and performs no discovery.

## Authority boundary

Even `RESOLVED_FOR_HANDOFF` preserves:

`allocation_source_provenance_verified=false`
`authoritative_allocation_source_verified=false`
`official_xone_snapshot_verified=false`
`official_registry_artifact_verified=false`
`xone_snapshot_eligibility_verified=false`
`xone_snapshot_xnt_allocation_binding_verified=false`
`allocation_semantics_verified=false`
`claim_state_verified=false`
`vesting_or_unlock_state_verified=false`
`xnt_issuance_verified=false`
`xnt_vesting_or_unlock_verified=false`
`october_6_unlock_applies_to_xone_verified=false`
`xone_xnt_conversion_verified=false`
`cross_chain_correlation_verified=false`
`public_service_promoted=false`
`scout_reliance_promoted=false`
`execution_authorized=false`

## Acceptance

Acceptance requires:

- deterministic resolver tests;
- exact-XONE structured export resolution;
- name-only downgrade;
- architecture-analogue preservation;
- hash-match and hash-mismatch tests;
- snapshot-block routing;
- Merkle routing;
- X1 program-schema routing;
- API routing with pinning boundary;
- content-addressed locator handling;
- ABI rejection;
- generic-config rejection;
- invalid-URL rejection;
- CMIS service-boundary test;
- prior allocation-source provenance regressions;
- prior allocation-record regressions;
- operational `NO_LEAD` proof with zero network discovery;
- full Liquidity Scout Tests;
- merge to `main`.

## Accepted operational result

Final accepted run #3 proves the intended idle state:

- `resolution_state=NO_LEAD`
- `NETWORK_CLIENT_IMPORTS=0`
- `network_discovery_performed=false`
- `network_request_count=0`
- `lead_supplied=false`
- `primary_artifact_candidate_discovered=false`
- `primary_artifact_resolved_for_handoff=false`
- `handoffs=[]`
- `execution_authorized=false`

The resolver and previous allocation-source/allocation-record regression suites passed, and full Liquidity Scout Tests #1838 passed.

The first CI cycle rejected the initial content-addressed completeness behavior: IPFS/Arweave correctly pinned the locator but did not satisfy the inherited repo/release provenance-completeness predicate. The accepted implementation treats a valid immutable content address plus retrieved content hash/source URL as complete content-addressed locator provenance while leaving other source classes strict. That behavior is regression-tested.

Evidence artifact:

- artifact id: `10034667373`
- digest: `sha256:c77ce4033a4421e9bb5b33bc6368b6ff1caa30008b511f78556a42915c5a67d5`

No real XONE allocation artifact was supplied during acceptance, so no candidate or handoff is claimed.

## Next gate

This resolver should remain idle in `NO_LEAD` until a new exact primary artifact appears.

When one appears, resolve it here first. Only a `RESOLVED_FOR_HANDOFF` artifact becomes eligible for the appropriate stronger verification contract.

Broad generic scraping is not automatically resumed.
