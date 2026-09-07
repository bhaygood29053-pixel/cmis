# Ethereum XONE Snapshot / Registry v1

Status: **IMPLEMENTATION FOR ISSUE #604 — NOT ACCEPTED UNTIL DETERMINISTIC + LIVE BOUNDED-SOURCE GATES + FULL TESTS PASS AND PR MERGES**

Contract:

`ethereum_xone_snapshot_registry/v1`

## Primary question

This contract is built around the XONE-holder question that matters:

> Which Ethereum XONE balances were captured by the XONE snapshot, at exactly what Ethereum block, and is that snapshot actually bound to an XNT allocation?

The contract does not use MoonParty as the answer and does not infer the snapshot from X1 mainnet launch, October 6, validator vesting, or ordinary XONE holder counts.

## Exact XONE identity

The ledger root is the already accepted Ethereum XONE contract:

`0x4DCDa2274899d9BbA3Bb6f5A852C107Dd6E4fE1c`

Creation block:

`18,609,736`

Snapshot reconstruction never selects a token by symbol or name.

## Four separate truth states

CMIS deliberately separates:

1. **snapshot source claim discovered** — a bounded source explicitly says XONE was snapshotted or names a holder registry;
2. **reconstructed registry verified** — CMIS can independently rebuild XONE balances at one exact Ethereum block;
3. **official XONE snapshot verified** — authoritative XONE/X1 evidence binds that exact block to the intended XONE snapshot;
4. **snapshot → XNT allocation binding verified** — separate evidence proves that the official snapshot controls XNT allocation/claim/vesting.

None of those states automatically promotes the next one.

## Source hierarchy

The live discovery gate covers bounded provenance-qualified sources:

- exact FairCrypto/XONE source and bounded commit-message history;
- FairCrypto/x1-app configuration and bounded commit-message history;
- official X1 web/docs targets;
- bounded X1 Report sitemap results as secondary reporting.

A direct Jack Levin statement can be accepted by the parser only when an exact public source is separately captured and supplied with source role `jack_levin_direct`.

The source extractor requires XONE and explicit snapshot/registry language in the same bounded context. It can preserve explicitly stated:

- date/time;
- Ethereum block;
- block/root/hash;
- exact Ethereum addresses;
- registry/CSV/JSON/IPFS links;
- XNT allocation/claim/vesting language.

It does not manufacture missing fields.

## Deterministic Ethereum reconstruction

Once an authoritative source supplies an exact snapshot block, the verifier can:

1. query the exact Ethereum chain;
2. bind the target to block number, block hash and timestamp;
3. fetch every canonical XONE `Transfer(address,address,uint256)` log from creation through the snapshot block in explicit contiguous ranges;
4. replay mint, transfer and burn directions into per-address balances;
5. reject wrong-contract logs, removed/malformed events, duplicate event identities, coverage gaps and negative balances;
6. compare the reconstructed holder sum with historical `totalSupply()` at the exact block;
7. verify a deterministic holder sample using historical `balanceOf(address)` at the same block;
8. emit a canonical sorted registry digest.

Canonical registry serialization:

```text
lowercase_address,balance_base_units\n
```

The SHA-256 of that exact serialization is the CMIS registry digest.

## Multi-RPC requirement

A reconstructed ledger is not enough to promote the snapshot as official.

Before `official_xone_snapshot_verified=true`, at least two distinct Ethereum RPC transport hosts must independently agree on:

- snapshot block and block hash;
- timestamp;
- XONE event count;
- holder count;
- historical total supply;
- reconstructed supply;
- canonical registry SHA-256.

The authoritative source's exact snapshot block must match that corroborated registry.

## Exact XONE identity binding

An authoritative snapshot statement must also be bound to the exact XONE identity. Promotion requires either:

- the source explicitly names the accepted XONE contract address; or
- the source is captured from the exact FairCrypto/XONE repository lineage.

A generic statement using a potentially ambiguous token name cannot promote the official snapshot state.

## X1 Labs ETH-address/native-XNT analogue

The public `x1-labs/xenblocks-airdrop` repository is inspected only as architecture context. Its public source demonstrates an ETH-address-keyed X1 airdrop tracker that can record native XNT airdrops.

That repository currently has **no XONE reference** in the bounded analogue corpus.

Therefore:

```text
x1_labs_airdrop_architectural_analogue = true
xone_snapshot_or_registry_binding_verified = false
```

It must never be substituted for the XONE snapshot or used to claim that an Ethereum XONE holder received XNT.

## Valid zero-result

A live PASS may find zero exact official snapshot candidates.

That means only:

```text
zero_official_candidates_are_scoped_corpus_evidence_only = true
private_or_unpublished_snapshot_absence_proven = false
```

It does not contradict a statement that a private or unpublished XONE snapshot may have been taken.

## Authority boundary

Unless separate evidence passes the corresponding gate:

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

## Next slice after acceptance

If the bounded gate finds no exact public snapshot block, the next work should be **snapshot provenance expansion**, not MoonParty deployment research: direct Jack/X1 historical posts or archives, XONE/X1 release artifacts, private/public registry references, Merkle roots, archived holder files, and any X1-side allocation list that contains Ethereum XONE addresses.

If an exact snapshot block is discovered, this contract is already capable of reconstructing and cryptographically digesting the complete XONE holder ledger at that block. The following gate is then the explicit **snapshot → XNT allocation binding**.
