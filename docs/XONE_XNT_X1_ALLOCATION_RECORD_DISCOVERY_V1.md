# X1-side XONE → XNT Allocation Record Discovery v1

Status: **ACCEPTED INTERNAL FOUNDATION** via Issue #616 / PR #617. XONE XNT X1 Allocation Record Discovery run #7 passed deterministic and live jobs at head `6d1b9bbedc7b21c0256fdff31c93407f250a053b`; Liquidity Scout Tests run #1823 passed; PR #617 merged as `2499511af489173a4a37af76674d03be533d1b2d`.

Contract:

`xone_xnt_x1_allocation_record_discovery/v1`

## Purpose

The accepted XONE snapshot track has already searched current public provenance, archived page text, and preserved historical application assets without recovering an authoritative Ethereum XONE snapshot block or registry artifact.

This contract changes the evidence direction. Instead of repeating generic snapshot searches, CMIS looks for **X1-side records keyed by Ethereum addresses** that could reveal how an XONE holder is represented in an XNT allocation, claim, registry, vesting, or distribution system.

The contract is discovery-first and read-only.

## Required exact pair

A candidate must contain both:

- an exact 20-byte Ethereum address;
- an exact X1/SVM public key that decodes to 32 bytes.

The pair must appear in XONE allocation/claim/registry context. A generic cross-chain address mapping is rejected.

## XONE identity boundary

Accepted Ethereum XONE identity:

`0x4DCDa2274899d9BbA3Bb6f5A852C107Dd6E4fE1c`

The parser distinguishes:

- `xone_specific_context=true` when the source explicitly names XONE in allocation-style context;
- `xone_identity_binding_verified=true` only when the exact accepted XONE contract is present in the same bounded record context.

Name-only XONE context remains a candidate, not exact identity proof.

## Preserved record fields

Where present, CMIS preserves without inventing values:

- Ethereum address;
- X1 pubkey;
- XNT/credit amount text;
- structured amount fields;
- claim state fields;
- vesting/lock/unlock fields;
- allocation/claim/record identifiers;
- source role;
- exact URL;
- repository path;
- pinned revision;
- observation time.

Missing fields remain missing.

## Structured and text extraction

The implementation supports:

- JSON / JSON-like allocation records;
- bounded text windows around exact Ethereum addresses;
- Ethereum-address-keyed registries where the address is a JSON object key;
- exact X1 pubkeys found in the same bounded record context.

The parser does not treat an ordinary wallet balance, current holder list, XONE ABI, generic XNT reward page, or unrelated airdrop mapping as XONE→XNT allocation proof.

## Duplicate and conflict handling

Records are grouped by:

`Ethereum address + X1 pubkey`

CMIS preserves all source record IDs and source URLs for the pair.

Conflicting amount observations are surfaced as an explicit conflict. They are not overwritten or averaged.

## Bounded live sources

The live gate scans a bounded current-public set:

1. `FairCrypto/x1-app`;
2. `FairCrypto/XONE`;
3. `x1-labs/xenblocks-airdrop`;
4. official `x1.xyz`, `docs.x1.xyz`, and `next.x1.xyz` source surfaces.

Repository traversal is bounded to ranked text/data paths and bounded file counts. The crawler does not enumerate arbitrary X1 accounts.

## Direct X1 qualification

Only exact X1 pubkeys already discovered from a qualifying record may be handed to finalized read-only X1 RPC:

`getAccountInfo(pubkey, {"encoding":"jsonParsed","commitment":"finalized"})`

CMIS may then preserve:

- account existence;
- finalized context slot;
- owner;
- executable flag;
- lamports;
- data size;
- parsed program/type when available.

Account existence proves only that exact account state. It does **not** prove allocation role.

## Valid zero result

A successful live gate may find zero qualifying allocation records.

That means only that the bounded public source set did not expose an exact Ethereum-address → X1-pubkey XONE allocation record.

It does not prove that no private, unpublished, deleted, unindexed, or future allocation registry exists.

Therefore:

`private_or_unpublished_allocation_registry_absence_proven=false`

## Authority boundary

Until separate verification proves otherwise:

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

- deterministic Ethereum-address validation tests;
- deterministic X1 pubkey validation tests;
- structured allocation-record extraction tests;
- generic-record false-positive rejection;
- XONE name-only vs exact-contract identity separation;
- duplicate/conflict grouping tests;
- finalized X1 account qualification boundary tests;
- CMIS service handoff tests;
- bounded live source-discovery gate;
- full Liquidity Scout Tests;
- merge to `main`.

## Accepted live result

Accepted run #7 covered:

- **3/3** bounded repositories available;
- **15** ranked repository files retrieved;
- **3/3** official X1 targets available;
- **0** qualifying allocation records;
- **0** candidates;
- **0** XONE-specific candidates;
- **0** exact-XONE-identity-bound candidates;
- **0** XNT-amount candidates;
- **0** amount conflicts.

Evidence artifact:

- artifact id: `10031487515`
- digest: `sha256:cd30ba9f18eb90c7ededecda6ab5b0949ed41aab567553575a008b8e20f663ac`

The accepted result was reached only after removing a live false-positive class. Run #4 had surfaced 12 apparent pairs from `FairCrypto/x1-app/public/abi/XONE.json`. Those alleged X1 pubkeys were Base58-looking slices of ABI/EVM bytecode, not typed allocation keys. Ordinary ABI artifacts and bytecode-substring matches are now rejected and covered by deterministic regression tests.

The accepted zero result is scoped to the bounded public source set. It does **not** prove that no private, unpublished, deleted, non-indexed, future, or separately distributed allocation registry exists.

## Next gate

Do not repeat the already-exhausted generic current-web / archive / archived-asset / bounded repository scan.

Move to **allocation-source provenance**: exact XONE-linked registry/export/API/Merkle artifacts, released CSV/JSON holder-allocation files, exact X1 program IDs/account schemas tied to allocation logic, or newly supplied/publicly discovered primary evidence.

If such an artifact is recovered, the following contract must separately prove **snapshot → XNT allocation binding**: source of eligibility, ratio/formula, exclusions/minimums, Ethereum→X1 mapping semantics, claim/allocation state, and whether the allocation is already fixed.
