# XONE Snapshot Archived Asset Graph Resolution v1

Status: **IMPLEMENTATION FOR ISSUE #613 — NOT ACCEPTED UNTIL DETERMINISTIC + LIVE ASSET-GRAPH + FULL TEST GATES PASS AND PR MERGES**

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

## Valid zero result

A successful bounded traversal may find zero semantic snapshot candidates.

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

## Next gate after acceptance

If the graph recovers a stable X/X Spaces URL, content-addressed artifact pointer, exact snapshot block or holder/export artifact, resolve that exact lead next.

If the public archived asset graph also yields no primary snapshot lead, narrow the evidence class further to **X1-side allocation-record discovery keyed by Ethereum XONE addresses** plus any non-indexed/publicly supplied snapshot artifact, rather than repeating generic web searches.
