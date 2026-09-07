# XONE Snapshot Archival Source Recovery v1

Status: **ACCEPTED INTERNAL FOUNDATION** via Issue #610 / PR #611. XONE Snapshot Archival Source Recovery run #4 passed deterministic and live archival jobs at head `105f7e9dd55c372afc7756a911ef79b9ab548ef9`; Liquidity Scout Tests run #1806 passed; PR #611 merged as `aa216ee6e49cc28ed969e990fd637577214a432c`.

Contract:

`xone_snapshot_archival_source_recovery/v1`

## Purpose

The accepted snapshot stack can already rebuild the complete Ethereum XONE holder ledger once an authoritative exact snapshot block is known.

The accepted `xone_snapshot_provenance_expansion/v1` pass showed that the bounded current-public corpus does not expose that block or a registry artifact.

This contract therefore moves one layer deeper: **historical/archival recovery**.

## Archive transport

The live gate uses the Internet Archive Wayback CDX index as a read-only discovery transport. The Wayback CDX API documents capture-index fields including original URL, capture timestamp, MIME type, status code, digest and length.

CMIS preserves those fields and builds a raw/identity replay URL for bounded retrieval.

Wayback is **not** treated as the publisher. Archive transport and original publisher remain separate facts.

## Original source authority

The contract recognizes archived originals on:

- `x1.xyz`
- `www.x1.xyz`
- `docs.x1.xyz`
- `next.x1.xyz`
- `xen.network`
- `www.xen.network`
- `preview.xen.network`

An archived page can only inherit the source role of its original host.

A capture on `web.archive.org` never becomes authoritative merely because it is archived.

## Bounded live targets

The live gate queries bounded historical captures from 2023–2026 for:

- XEN Network root and XONE-oriented paths;
- X1 root, XONE and snapshot-oriented paths;
- Next X1 root/XONE paths;
- X1 Docs root;
- indexed Jack Levin history via XspaceGPT and TwStalker when available.

The current public XspaceGPT index is relevant because it exposes the historical Jack-hosted/Cyphereus Prime X Space **"XONE mint is live"** dated November 20, 2023. That is historical context only unless a stable original X/X Spaces URL and snapshot-specific statement are recovered.

## Stable X URL recovery

Mirror/index text is scanned for stable original URLs such as:

```text
https://x.com/mrJackLevin/status/<id>
https://x.com/i/spaces/<id>
```

Recovering a stable URL proves only that the original URL was identified.

It does **not** prove the content of that X post or Space, and does not set direct Jack authority until the primary source itself is retrieved and semantically verified.

## Capture states

The contract keeps separate:

```text
archival_capture_discovered
archival_capture_retrieved
stable_primary_url_recovered
direct_primary_archival_source_recovered
snapshot_artifact_candidate_discovered
authoritative_exact_snapshot_block_discovered
official_xone_snapshot_verified
official_registry_artifact_verified
xone_snapshot_eligibility_verified
xone_snapshot_xnt_allocation_binding_verified
```

## False-positive controls

Ordinary XONE pages, ABI JSON, current holder counts and generic XNT airdrop architecture are not snapshot proof.

The archival content must contain explicit XONE plus snapshot/registry/artifact semantics before a provenance candidate is produced.

## Direct-chain handoff

If exactly one authoritative Ethereum snapshot block is recovered from preserved primary-source content, the live gate automatically invokes the accepted `ethereum_xone_snapshot_registry/v1` verifier.

That verifier still requires:

- canonical XONE Transfer replay from creation block;
- historical `totalSupply()` agreement;
- deterministic historical `balanceOf()` checks;
- canonical registry SHA-256;
- matching registry proofs from two distinct Ethereum RPC hosts.

Only then may `official_xone_snapshot_verified=true`.

Even then, snapshot eligibility and snapshot→XNT allocation remain separate gates.

## Accepted live result

Run #4 established bounded archival coverage across the selected historical XEN/X1/X1 Docs surfaces:

- **9/9** Wayback CDX queries were available;
- **93** distinct archival captures were discovered;
- **11** bounded captures were successfully replayed after deterministic host/time diversification;
- CDX coverage included original hosts `xen.network`, `x1.xyz`, `next.x1.xyz`, and `docs.x1.xyz`;
- the XspaceGPT Jack Levin index was available and contained XONE historical context, but no explicit snapshot term;
- TwStalker returned HTTP 403 and was retained as an availability failure rather than negative content evidence;
- some selected Wayback replays, including XEN captures, hit transient connection-refused failures and were preserved as availability evidence.

The accepted semantic result was:

```text
stable_primary_urls = 0
archival_provenance_candidates = 0
direct_primary_archival_candidates = 0
authoritative_exact_snapshot_blocks = 0
official_xone_snapshot_verified = false
```

Evidence artifact:

- artifact id: `10029502671`
- digest: `sha256:136d96e7aba8d5f50b4d694add915537cf171d9d6ab7efa9f0f55fd0b22db69d`

This does **not** mean every discovered capture was successfully replayed and does not prove the snapshot never existed. It means the bounded public archive sources that were successfully retrieved did not expose an authoritative exact snapshot block or registry artifact.

## Fail-closed zero result

A live PASS can validly find no authoritative block.

That means only:

```text
zero_authoritative_blocks_are_scoped_archival_evidence_only = true
private_or_unpublished_snapshot_absence_proven = false
```

It must not be reported as proof that Jack Levin/X1 never took an Ethereum XONE snapshot.

## Authority boundary

Until separate evidence proves otherwise:

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

## Next gate after recovery

If archival recovery produces an exact block or registry artifact, immediately run the accepted ledger reconstruction and then prove **snapshot → XNT allocation binding**.

If it produces only stable primary links, the next action is direct retrieval/verification of those exact primary sources.

The accepted archival pass produced no authoritative lead. The next exact investigation should therefore move to **archived asset-graph / primary-source resolution**: enumerate historical root-page links, JavaScript bundles, manifests, JSON/static assets and stable social-source identifiers from recovered XEN/X1 captures, then search those preserved assets for XONE/snapshot/holder/registry/XNT semantics. Only after those public archival asset surfaces are exhausted should the evidence class be narrowed further toward non-indexed or unpublished material such as private holder exports, deleted social content not retained by public archives, distribution files or internal X1/FairCrypto allocation records.
