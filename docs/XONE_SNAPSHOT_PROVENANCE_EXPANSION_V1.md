# XONE Snapshot Provenance Expansion v1

Status: **ACCEPTED INTERNAL FOUNDATION** via Issue #607 / PR #608. XONE Snapshot Provenance Expansion run #6 passed deterministic and live jobs at head `beedae86c92d4919abccdc975f84094a3ebc9de0`; Liquidity Scout Tests run #1799 passed; PR #608 merged as `ff0648a3768ce1f4f1307dc66e24baa8c920746a`.

Contract:

`xone_snapshot_provenance_expansion/v1`

## Purpose

The accepted `ethereum_xone_snapshot_registry/v1` contract can reconstruct the complete Ethereum XONE holder ledger once an authoritative exact snapshot block is known.

The missing fact is now **provenance**:

> Where did Jack Levin / FairCrypto / X1 define or record the XONE Ethereum holder snapshot, and what exact block or registry artifact was used?

This contract expands that search without weakening the evidence boundary.

## Source hierarchy

Candidates are ranked by provenance strength:

1. exact FairCrypto/XONE repository or official X1 source;
2. direct Jack Levin / X1 statement with a stable primary-source URL;
3. FairCrypto/x1-app source/history;
4. x1-labs source that explicitly binds XONE to an X1 allocation mechanism;
5. X1 Report;
6. indexed mirrors and transcript indexes used only to locate a primary source.

A mirror never becomes authoritative merely because it quotes or indexes Jack.

## Historical surfaces

The live gate inspects bounded public surfaces including:

- FairCrypto/XONE current revision, up to 100 commit messages, tags, releases, recursive tree paths and a bounded set of candidate file contents;
- FairCrypto/x1-app using the same bounded history/tree/content process;
- x1-labs/xenblocks-airdrop for XONE-specific binding or architecture clues;
- official X1 web/docs through the accepted dedicated scraper;
- up to 50 ranked X1 Report pages;
- indexed Jack Levin historical surfaces, including the XspaceGPT host index and TwStalker profile when available.

The indexed X Spaces surface is useful because public indexing currently exposes a Jack-hosted/Cyphereus Prime space titled **"XONE mint is live"** dated **November 20, 2023**. That is a historical lead only. It is not evidence that the later holder snapshot occurred on that date.

## Candidate classes

The contract distinguishes:

- `snapshot_statement` — XONE plus explicit snapshot/registry semantics;
- `artifact_reference` — XONE plus holder/registry/Merkle/allocation/export/file indicators;
- `historical_context` — XONE launch/mint/roadmap material useful for locating adjacent primary sources.

Repository filenames can create path-level artifact leads, but path-only results are explicitly marked and cannot count as recovered primary-source content.

## Extracted evidence

A candidate can preserve, when explicitly present:

- Ethereum snapshot block;
- block/root/digest hashes;
- exact XONE contract address;
- date/time;
- CSV/JSON/JSONL/TSV references;
- IPFS / Arweave references;
- holder / balance / eligibility semantics;
- XNT allocation/claim/vesting/unlock language;
- source URL, repository path and revision.

## Promotion boundary

The contract keeps these states separate:

```text
provenance_candidate_discovered
direct_primary_source_recovered
snapshot_artifact_candidate_discovered
authoritative_exact_snapshot_block_discovered
official_xone_snapshot_verified
official_registry_artifact_verified
xone_snapshot_eligibility_verified
xone_snapshot_xnt_allocation_binding_verified
```

An exact authoritative block is only eligible when:

- the source role is FairCrypto/XONE, official X1 or direct Jack Levin;
- explicit XONE snapshot semantics are present;
- exactly one Ethereum block is stated;
- the exact XONE contract is stated, or the evidence is from the exact FairCrypto/XONE repository lineage.

## Automatic direct-chain handoff

If the live provenance gate discovers exactly one authoritative snapshot block, it automatically invokes the already-accepted `ethereum_xone_snapshot_registry/v1` path.

That path must:

- replay canonical XONE Transfer logs from creation through the snapshot block;
- match historical `totalSupply()`;
- verify deterministic historical `balanceOf()` samples;
- compute the canonical registry SHA-256;
- receive matching proofs from two distinct Ethereum RPC hosts.

Only then can `official_xone_snapshot_verified=true`.

Even then, the snapshot→XNT allocation binding remains a separate gate.

## Accepted live result

Run #6 expanded the bounded public provenance corpus across:

- both FairCrypto repositories: `FairCrypto/XONE` and `FairCrypto/x1-app`;
- `x1-labs/xenblocks-airdrop`;
- **4** available official X1 web/docs targets;
- **13** available ranked X1 Report pages;
- **1** available indexed Jack Levin historical surface.

After the false-positive regression was tightened so ordinary XONE ABI/config JSON could not masquerade as snapshot provenance, the accepted result was:

```text
provenance_candidates = 0
direct_primary_source_candidates = 0
snapshot_artifact_candidates = 0
indexed_mirror_candidates = 0
authoritative_exact_snapshot_blocks = 0
official_xone_snapshot_verified = false
```

The available indexed Jack surface contained XONE historical material but no explicit snapshot term. The absence of a candidate is therefore a bounded public-provenance result, not a claim that Jack/X1 never took a private or unpublished snapshot.

Evidence artifact:

- artifact id: `10028368038`
- digest: `sha256:bd3db1a9804a070e1a8017fd660db4bad3eb0802ad114d3de0ebc5d54fa1af88`

Because no authoritative exact block emerged, the automatic direct-chain registry reconstruction was correctly not triggered.

## Fail-closed zero result

The accepted PASS produced zero authoritative snapshot blocks.

That means:

```text
zero_authoritative_blocks_are_scoped_public_provenance_only = true
private_or_unpublished_snapshot_absence_proven = false
```

CMIS must not turn a public-search miss into a claim that Jack/X1 never took the snapshot.

## Non-substitutes

The following do not establish the XONE snapshot:

- X1 mainnet launch date;
- October 6 validator unlock;
- validator testnet reward vesting;
- MoonParty deployment or XNT-credit semantics;
- current XONE holder counts;
- generic Ethereum-address keyed native-XNT airdrop infrastructure;
- token symbols or names alone.

## Authority boundary

Until separately proven:

```text
official_xone_snapshot_verified = false
official_registry_artifact_verified = false
xone_snapshot_eligibility_verified = false
xone_snapshot_xnt_allocation_binding_verified = false
xnt_issuance_verified = false
xnt_vesting_or_unlock_verified = false
october_6_unlock_applies_to_xone_verified = false
xone_xnt_conversion_verified = false
cross_chain_correlation_verified = false
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

## Next gate

The next work remains **primary-source snapshot recovery**, but should now move beyond the already-exhausted bounded public GitHub/current-site corpus toward provenance surfaces that can still contain unpublished or older material:

- stable/direct Jack Levin historical X links or archives;
- archived X1/FairCrypto/XEN pages and release material;
- registry/CSV/JSON/IPFS/Arweave references;
- Merkle roots or holder-export artifacts;
- X1-side allocation/claim records keyed by Ethereum addresses.

If an exact snapshot block/artifact is recovered and verified, the next contract is the explicit **XONE snapshot → XNT allocation binding**: eligibility formula, exclusions/minimums, allocation ratio, Ethereum→X1 wallet mapping, claim/allocation record and XONE-specific vesting/unlock state.
