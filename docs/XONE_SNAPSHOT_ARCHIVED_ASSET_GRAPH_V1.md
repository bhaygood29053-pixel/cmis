# XONE Snapshot Archived Asset Graph Resolution v1

Status: **ACCEPTED INTERNAL FOUNDATION** via Issue #613 / PR #614. XONE Snapshot Archived Asset Graph run #4 passed deterministic and live jobs at head `41506c866badadebb2a1c767ce573b7b0abeee60`; Liquidity Scout Tests run #1813 passed; PR #614 merged as `2cedaf6431093262495ad713c60b199cc7164dc0`.

Contract:

`xone_snapshot_archived_asset_graph_resolution/v1`

## Purpose

The accepted public-page and archival-page searches have not recovered the Ethereum XONE holder snapshot block or registry artifact.

That does not mean the evidence was never public. Modern application pages often keep important configuration and data outside visible page text in:

- JavaScript bundles;
- Next.js manifests;
- JSON/static assets;
- source maps;
- CSV/TSV/JSONL exports;
- API/data path strings;
- IPFS / Arweave pointers;
- stable X status or X Spaces identifiers.

This contract resolves that preserved historical **asset graph**.

## Graph provenance

Every graph edge preserves:

```text
root capture id
parent capture id
parent original URL
parent archive timestamp
parent archive digest
graph depth
asset original URL
asset kind
discovery basis
same-origin status
Wayback traversal eligibility
```

A retrieved asset additionally preserves its own exact Wayback CDX capture metadata, content type, byte count and SHA-256.

## Bounded traversal

Traversal is deliberately bounded:

- graph depth is at most 2;
- root captures are selected across historical `xen.network`, `x1.xyz`, `next.x1.xyz` and `docs.x1.xyz`;
- references per node are capped;
- exact asset CDX lookups are capped;
- asset replays are capped;
- response bytes are bounded;
- traversal cannot escape the original same-origin application host through Wayback.

External URLs may be preserved as leads but are not automatically crawled.

## Asset classes

The resolver distinguishes:

- `javascript`;
- `manifest`;
- `json`;
- `source_map`;
- `data`;
- `html`;
- stable `x_status` / `x_space`;
- `ipfs`;
- `arweave`;
- other/external links.

Only same-origin application assets in the traversable classes are automatically resolved through exact Wayback CDX capture metadata.

## Semantic boundary

Retrieved assets are passed through the accepted XONE snapshot provenance parser.

A semantic candidate requires meaningful XONE snapshot/registry/allocation context. Ordinary:

- XONE ABI JSON;
- XONE contract configuration;
- token name/symbol references;
- current holder counts;

do not become snapshot evidence.

## Archive authority

Wayback remains preservation transport only.

An archived `x1.xyz`, `docs.x1.xyz`, `next.x1.xyz` or `xen.network` asset may preserve content from an authoritative original host, but the archive host itself adds no authority.

A stable:

```text
https://x.com/<user>/status/<id>
https://x.com/i/spaces/<id>
```

recovered inside an asset is still only a primary-source locator until the original source is retrieved and semantically verified.

## Content-addressed pointers

IPFS and Arweave references are preserved separately.

A pointer does not prove the referenced object is the official registry. It becomes a future artifact candidate only after the object is retrieved, content-hashed and bound by authoritative XONE/X1 provenance.

## Automatic snapshot handoff

If exactly one authoritative exact Ethereum XONE snapshot block emerges from an archived authoritative-host asset with exact XONE identity binding, the live gate automatically invokes the accepted `ethereum_xone_snapshot_registry/v1` verifier.

That still requires:

- canonical XONE Transfer replay from creation block;
- historical `totalSupply()` agreement;
- deterministic historical `balanceOf()` checks;
- canonical registry SHA-256;
- two distinct Ethereum RPC transports agreeing.

Only then may `official_xone_snapshot_verified=true`.

Snapshot eligibility and snapshot→XNT allocation remain separate contracts even after that.

## Accepted live result

Run #4 successfully traversed preserved historical application assets behind the selected XEN/X1 surfaces:

- **41** root captures were discovered;
- **6** root captures were successfully replayed;
- **237** asset-graph edges were extracted;
- **136** edges were same-origin and eligible for bounded Wayback asset resolution;
- **4** archived application assets were successfully retrieved and content-hashed;
- **0** semantic XONE snapshot candidates were found;
- **0** stable primary X/X Spaces URLs were recovered;
- **0** IPFS/Arweave content-addressed pointers were recovered;
- **0** authoritative exact Ethereum snapshot blocks were recovered.

Evidence artifact:

- artifact id: `10031024146`
- digest: `sha256:83369e886049a393cc9042ba4d0faf6f62fd148712a45e39028119d35ef88e3e`

No holder-ledger reconstruction was triggered because no authoritative exact block emerged. The accepted result therefore proves bounded archived-asset traversal and negative findings only inside that inspected graph. It does **not** prove that no private, unpublished, deleted-unarchived, non-indexed or unpreserved snapshot source exists.

## Valid zero result

The accepted bounded traversal found zero semantic snapshot candidates.

That means only:

```text
zero_semantic_candidates_are_scoped_asset_graph_evidence_only = true
private_or_unpublished_snapshot_absence_proven = false
```

It does not prove absence from unpreserved assets, deleted/unindexed social content, private holder exports or internal allocation records.

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

## Next gate

The current-public pages, public GitHub provenance, archived page text, and bounded archived application asset graph have now all failed to expose an authoritative XONE snapshot block or registry artifact.

The next exact investigation is therefore **X1-side XONE→XNT allocation-record discovery keyed by Ethereum XONE addresses**. Search for exact records that can bind:

- an Ethereum address;
- an X1 address/pubkey;
- an XNT allocation amount;
- an allocation/claim identifier;
- a Merkle leaf/root or registry row when present;
- claim state;
- vesting/unlock state;
- the source artifact/account/program that owns the record.

A discovered allocation record is not automatically proof of snapshot eligibility or issuance. Exact artifact/account identity, semantics and XONE provenance must be verified separately.

Any non-indexed snapshot artifact supplied later can still be handed directly to the accepted snapshot-registry verifier.
