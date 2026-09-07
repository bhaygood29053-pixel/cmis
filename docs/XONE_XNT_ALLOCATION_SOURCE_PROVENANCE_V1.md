# XONE → XNT Allocation Source Provenance v1

Status: **ACCEPTED INTERNAL FOUNDATION** via Issue #619 / PR #620. XONE XNT Allocation Source Provenance run #6 passed deterministic and live jobs at head `1fa258507b61a49ec000e8228534cd65476dac7a`; Liquidity Scout Tests run #1832 passed; PR #620 merged as `fe541b9969aa851e658b7abb4bf02c2e734be295`.

Contract:

`xone_xnt_allocation_source_provenance/v1`

## Purpose

The accepted XONE/XNT investigation has already completed:

- exact Ethereum XONE identity;
- canonical Ethereum event observation;
- burn/redeemer semantics;
- exact conversion-address candidate discovery;
- X1-side XNT mechanism discovery;
- exact X1 binding discovery;
- Ethereum snapshot/registry verifier;
- current-public snapshot provenance;
- bounded archival recovery;
- archived application asset-graph traversal;
- X1-side allocation-record discovery keyed by Ethereum addresses.

The accepted allocation-record run produced zero qualifying public records after ABI/bytecode false positives were removed and regression-tested.

This contract therefore changes the search target from **holder rows** to **the source that would own or publish those rows**.

## Qualifying source classes

CMIS recognizes the following concrete provenance classes:

1. `registry_export_artifact`
2. `structured_allocation_file`
3. `api_endpoint`
4. `merkle_artifact`
5. `content_addressed_artifact`
6. `x1_program_schema`
7. `release_asset`

A candidate may belong to more than one class.

Examples include:

- `xone-allocations.csv`;
- a JSON/JSONL holder-allocation export;
- an HTTPS API endpoint explicitly serving XONE allocation or claim data;
- a Merkle root/tree/proof source;
- an IPFS CID or Arweave transaction id tied to XONE allocation data;
- an exact X1 program ID with an IDL/account/PDA schema explicitly tied to XONE-derived XNT allocations;
- a release asset or manifest that names one of those artifacts.

## Exact XONE identity

Accepted Ethereum XONE contract:

`0x4DCDa2274899d9BbA3Bb6f5A852C107Dd6E4fE1c`

The contract preserves separate states:

- `xone_named`
- `xone_semantic_binding_discovered`
- `exact_xone_contract_mentioned`
- `xone_source_binding_verified`
- `qualifying_xone_allocation_source_candidate`

Name-only XONE context may create a bounded candidate, but exact source binding requires the accepted XONE contract identity in the same source context.

## Architecture analogue boundary

Public `x1-labs/xenblocks-airdrop` is useful because it exposes a real X1/SVM airdrop architecture:

- exact program IDs;
- Anchor configuration;
- IDL/type files;
- account/PDA schemas;
- ETH-address-keyed on-chain record design.

It is **not** XONE allocation evidence unless XONE is explicitly bound.

Therefore analogue evidence may be preserved as:

`architecture_analogue=true`

while simultaneously preserving:

`xone_source_binding_verified=false`
`qualifying_xone_allocation_source_candidate=false`

This prevents generic XNT/XNM airdrop machinery from being promoted into XONE conclusions.

## False-positive boundaries

The extractor rejects or fails closed on:

- ordinary EVM ABI files by themselves;
- container/package registry references such as `ghcr.io`;
- generic XNT reward/validator rules;
- generic airdrop machinery with no XONE binding, except when deliberately marked as architecture analogue;
- arbitrary Ethereum addresses;
- arbitrary X1 pubkeys;
- source import paths with no allocation-source semantics;
- ordinary XONE config/application JSON with no provenance role;
- MoonParty as a substitute for the current evidence target.

The ABI exclusion is especially important because the previous live allocation-record gate demonstrated that ABI/EVM bytecode can contain Base58-looking substrings that are not X1 keys.

## Provenance fields

Where present, each candidate preserves:

- source id / source role;
- exact HTTPS source URL;
- repository path;
- pinned revision;
- release name;
- content type;
- SHA-256 of retrieved text;
- source classes;
- structured filenames;
- API URLs;
- Merkle roots;
- IPFS CIDs;
- Arweave transaction ids;
- X1 program IDs;
- XONE semantic/exact-contract flags;
- source provenance field completeness;
- exact bounded evidence excerpt;
- observation time.

Missing values remain missing.

## Bounded live source set

The live gate covers:

### FairCrypto/x1-app

- repository metadata and pinned default-branch revision;
- provenance-shaped paths only;
- release metadata/assets;
- source references likely to own or expose registry/export/API/Merkle/program-schema data.

### FairCrypto/XONE

Same bounded provenance classes as above.

### x1-labs/xenblocks-airdrop

Used as an architecture analogue only.

Forced analogue paths include:

- `Anchor.toml`;
- `.env.example`;
- `target/idl/xenblocks_airdrop_tracker.json`;
- `target/types/xenblocks_airdrop_tracker.ts`;
- on-chain program source;
- PDA/type definitions;
- ETH-only PDA migration design.

### Official X1 surfaces

- `https://x1.xyz/`
- `https://docs.x1.xyz/`
- `https://next.x1.xyz/`

Only exact provenance-shaped references count as candidates.

## Release discovery

The gate queries GitHub release metadata for all three repositories.

A release is not automatically an allocation source.

Release candidates require allocation-source semantics plus a concrete provenance class such as a structured allocation file, API endpoint, Merkle source, content-addressed artifact, or typed program schema.

## Content hashing

Retrieved repository and official-source text is SHA-256 hashed.

If a supplied hash does not match the actual content, extraction fails closed.

This prevents provenance rows from claiming a content digest that was not calculated from the inspected artifact.

## Valid zero result

A successful bounded live run may produce zero qualifying XONE allocation-source candidates.

That means only:

> the inspected public repository/release/official source classes did not expose a qualifying XONE-derived XNT allocation source.

It does **not** prove that no:

- private allocation registry;
- unpublished export;
- future release;
- deleted/unindexed file;
- separately distributed CSV/JSON;
- private API;
- unpublished Merkle tree;
- unreleased X1 program/account mapping

exists.

Therefore:

`private_or_unpublished_allocation_source_absence_proven=false`

## Promotion boundary

Discovery and provenance fields remain weaker than authoritative allocation truth.

Until separately proven:

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

## Automatic handoff rules

If a qualifying source emerges:

- holder/export artifact → hand to `xone_xnt_x1_allocation_record_discovery/v1`;
- authoritative snapshot source/block → hand to `ethereum_xone_snapshot_registry/v1`;
- Merkle source → hand to a future snapshot→allocation binding verifier;
- exact X1 program/account schema → bounded finalized X1 qualification;
- no issuance/vesting/unlock claim without separate direct proof.

## Acceptance

Acceptance requires:

- provenance-class extraction tests;
- exact-XONE vs name-only source-binding tests;
- API extraction tests;
- Merkle extraction tests;
- IPFS/Arweave extraction tests;
- X1 program-schema extraction tests;
- architecture-analogue separation tests;
- ABI false-positive rejection;
- container-registry false-positive rejection;
- content-hash verification;
- deterministic summary/dedup behavior;
- CMIS service-boundary preservation;
- bounded live source gate;
- full Liquidity Scout Tests;
- merge to `main`.

## Accepted live result

Final accepted run #6 covered:

- **3/3** bounded repositories available;
- **41** provenance-shaped repository files retrieved;
- **3/3** release queries available;
- **3/3** official X1 targets available;
- **10** surviving architecture-analogue candidates;
- **0** qualifying XONE allocation-source candidates;
- **0** exact-XONE-source-bound candidates.

Final source-class counts:

- `x1_program_schema = 10`
- `api_endpoint = 0`
- `merkle_artifact = 0`
- `content_addressed_artifact = 0`
- `registry_export_artifact = 0`
- `release_asset = 0`
- `structured_allocation_file = 0`

The 10 analogue artifacts are all from `x1-labs/xenblocks-airdrop` and are limited to real program/Anchor/IDL/PDA/account-schema surfaces. Every one is explicitly non-XONE: `xone_named=false`, `exact_xone_contract_mentioned=false`, and `qualifying_xone_allocation_source_candidate=false`.

Earlier live cycles were intentionally not accepted at face value. Manual inspection found source-id semantic leakage, generic TypeScript export/config noise, generic RPC URLs, a `pda` substring false match inside `update`, and IDL dual-classification. Each defect was fixed and converted into deterministic regression coverage before the accepted run.

Evidence artifact:

- artifact id: `10033477532`
- digest: `sha256:26e43c87579aad3abbd6932df2e54923f73e2f575abf8ab880a5070056d6811f`

The accepted zero-XONE result is scoped to this bounded public source set. It does **not** prove that no private, unpublished, deleted, separately distributed, or future XONE allocation source exists.

## Next gate

The accepted live result is zero for XONE-qualified public allocation-source provenance, so do **not** repeat the same current repository/release/official-page corpus.

The remaining path is source-specific primary-artifact resolution / evidence intake. Resume only when an exact lead appears, such as:

- an XONE registry/export;
- holder-allocation CSV/JSON/JSONL;
- authoritative allocation/claim API;
- Merkle root/tree/proof source;
- IPFS/Arweave allocation artifact;
- exact deployed X1 program/account schema explicitly tied to XONE;
- an externally supplied primary artifact with preservable provenance.

A recovered source must then pass exact source verification and a separate **snapshot → XNT allocation binding** contract before any issuance, vesting, unlock, October 6, or cross-chain conclusion is eligible.
