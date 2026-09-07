# XONE/XNT Conversion Intelligence v1

Status: **ACCEPTED INTERNAL FOUNDATION** via Issue #575 / PR #578. Dedicated XONE/XNT Scraper run #2 and Liquidity Scout Tests run #1744 passed before merge. This capability remains deliberately separate from the generic `cmis_web_discovery/v1` provider registry, non-promoted for public/Scout reliance, and `execution_authorized=false`.

## Purpose

Collect and preserve candidate evidence about the Ethereum XONE -> X1 XNT migration/conversion without turning web statements into verified chain facts.

Contracts:

- `xone_xnt_conversion_scraper/v1`
- `xone_xnt_conversion_intelligence/v1`

## Initial source registry

| source_id | source | role | boundary |
| --- | --- | --- | --- |
| `x1_official` | X1 | official X1 web | `x1.xyz`, `www.x1.xyz` |
| `x1_docs` | X1 Docs | official X1 documentation | `docs.x1.xyz`, `next.x1.xyz` |
| `x1report` | X1 Report | third-party X1 reporting | `x1report.com`, `www.x1report.com` |

X1 Report also has a registered bounded sitemap entrypoint at `https://x1report.com/sitemap.xml`. Sitemap ranking prioritizes XONE explicitly, then XNT, conversion, migration, vesting, unlock, lockup, investor, snapshot, claim, burn, Jack Levin and October 6 references.

The source registry remains intentionally narrow. The accepted chain now includes exact Ethereum XONE identity/events/burn semantics, conversion-address discovery, X1 XNT mechanism/binding discovery, Ethereum snapshot/registry verification, current/archival snapshot provenance, archived asset-graph traversal, X1-side allocation-record discovery, `xone_xnt_allocation_source_provenance/v1`, and the lead-driven `xone_xnt_primary_allocation_artifact_resolution/v1` via #622 / PR #623. Bounded public provenance found no qualifying XONE allocation source, so broad discovery is paused. Resolver run #3 accepted the intentional `NO_LEAD` state with zero network-client imports and zero discovery requests, while full Liquidity Scout Tests #1838 passed. CMIS can now safely ingest one already-retrieved primary artifact, verify locator/hash/exact-XONE prerequisites, and classify it for a stronger verifier without promoting allocation/issuance truth. No actual XONE primary allocation artifact has yet been resolved. Earlier MoonParty work remains accepted historical background and does not substitute for snapshot/allocation proof.

## Candidate topics

The deterministic extractor recognizes bounded XONE-related statements about:

- conversion/migration and ratios;
- burns;
- eligibility and snapshots;
- claims/redemption;
- lockups, vesting and unlock dates;
- transferability;
- distribution/allocation/airdrops;
- contract/program references;
- Ethereum/X1 cross-chain context.

It also extracts candidate ratios, percentages, calendar dates, Ethereum-style addresses and XONE/XNT amounts. These values remain source-reported candidates.

## Historical and conflict handling

Claims are immutable candidate rows keyed by a SHA-256 identity over source, URL and excerpt. Review groups are built by topic. If two claims for one topic contain different extracted ratios, percentages, dates, addresses or token amounts, the group sets:

- `potential_conflict=true`
- `conflict_verified=false`

A potential conflict is a review signal, not a conclusion that either source is wrong or that the statements are actually contradictory.

## Cross-chain proof rule

An Ethereum-side XONE burn, lock or transfer **does not prove** XNT was issued on X1.

A web statement **does not prove** either side of the migration.

Candidate records emit explicit handoffs for:

1. exact Ethereum XONE token identity and event verification;
2. exact X1 XNT allocation/vesting/claim verification;
3. CMIS cross-chain correlation between the two independently verified events.

Only a later accepted corroboration contract may elevate those direct-chain facts.

## Authority boundary

Every scraper/service response keeps:

```text
discovery_state = DISCOVERED
web_claim_verified = false
ethereum_event_verified = false
x1_event_verified = false
cross_chain_correlation_verified = false
freshness_verified = false
source_independence_verified = false
cmis_verified = false
public_service_promoted = false
scout_reliance_promoted = false
cmis_promotable = false
execution_authorized = false
```

The capability is read-only. It does not connect a wallet, sign requests, construct transactions, submit transactions, burn XONE, claim XNT, or authorize execution.

## Operator examples

Scrape one explicit X1 Report page:

```bash
PYTHONPATH=. python scripts/scrape_xone_xnt_conversion.py \
  x1report \
  https://x1report.com/article/jack-levin-answers-xen-x1-community-questions
```

Rank and scrape bounded X1 Report sitemap candidates:

```bash
PYTHONPATH=. python scripts/scrape_xone_xnt_conversion.py \
  x1report \
  --sitemap \
  --max-urls 20
```

## Next acceptance slices

1. **COMPLETE:** exact Ethereum XONE ERC-20 identity accepted under `ethereum_xone_identity/v1` via #580 / PR #581;
2. **COMPLETE:** bounded canonical Ethereum XONE event observer accepted under `ethereum_xone_event_observer/v1` via #583 / PR #584;
3. **COMPLETE:** XONE burn/redeemer and migration-sink semantic foundation accepted under `ethereum_xone_migration_sink_semantics/v1` via #586 / PR #587; burn accounting is verified, but no migration sink is identified;
4. **COMPLETE:** exact-address conversion-candidate discovery/qualification accepted under `xone_xnt_conversion_candidate_discovery/v1` via #589 / PR #590; the first bounded X1 Report live corpus yielded 0 candidate claims / 0 exact address candidates, with no global-absence inference;
5. **COMPLETE FOUNDATION:** independent X1-side XNT reward/distribution/vesting rule discovery accepted under `x1_xnt_distribution_mechanism_discovery/v1` via #592 / PR #593; the official X1 rewards page yielded 17 bounded rule claims and 0 exact X1 pubkey candidates, with no global-absence inference;
6. **COMPLETE BOUNDED FOUNDATION:** exact X1-side binding discovery accepted under `xone_xnt_x1_binding_discovery/v1` via #595 / PR #596; run #4 inspected 4/4 official X1 targets plus 13/13 ranked X1 Report pages and found 0 explicit XONE/XNT conversion claims / 0 exact X1 binding candidates, with no global-absence inference;
7. **HISTORICAL / NON-PRIORITY:** FairCrypto MoonParty source semantics and bounded deployment discovery remain accepted via #598/#599 and #601/#602, but MoonParty is not the current XONE/XNT roadmap target;
8. **COMPLETE PRIMARY FOUNDATION:** Ethereum XONE holder snapshot/registry verification accepted under `ethereum_xone_snapshot_registry/v1` via #604 / PR #605. Run #1 searched 8 FairCrypto source/history targets, 4 official X1 targets and 13 available X1 Report pages and found 0 explicit snapshot claims / 0 official snapshot candidates / 0 authoritative exact snapshot blocks. The result is scoped public-corpus evidence only;
9. **COMPLETE BOUNDED PROVENANCE EXPANSION:** `xone_snapshot_provenance_expansion/v1` accepted via #607 / PR #608. Run #6 covered both FairCrypto repositories, x1-labs/xenblocks-airdrop, 4 official X1 targets, 13 available X1 Report pages and 1 indexed Jack-history surface; after false-positive filtering it produced 0 provenance candidates / 0 artifact candidates / 0 authoritative exact snapshot blocks. No global/private-snapshot absence inference is allowed;
10. **COMPLETE BOUNDED ARCHIVAL RECOVERY:** `xone_snapshot_archival_source_recovery/v1` accepted via #610 / PR #611. Run #4 had 9/9 CDX queries available, 93 captures discovered, 11 diversified captures successfully replayed, 0 stable primary URLs, 0 archival provenance candidates and 0 authoritative exact snapshot blocks. Replay/index availability failures are preserved and no private/global absence inference is allowed;
11. **COMPLETE ARCHIVED ASSET-GRAPH RESOLUTION:** `xone_snapshot_archived_asset_graph_resolution/v1` accepted via #613 / PR #614. Run #4 discovered 41 root captures, replayed 6 roots, extracted 237 asset edges / 136 same-origin traversable edges, retrieved 4 archived application assets, and found 0 semantic snapshot candidates / 0 stable primary social URLs / 0 content-addressed pointers / 0 authoritative exact snapshot blocks. No private/global absence inference is allowed;
12. **COMPLETE BOUNDED X1 ALLOCATION-RECORD DISCOVERY:** `xone_xnt_x1_allocation_record_discovery/v1` accepted via #616 / PR #617. Run #7 covered 3/3 repositories, 15 ranked repository files and 3/3 official X1 targets and found 0 qualifying records / 0 candidates / 0 exact-XONE-bound candidates / 0 XNT-amount candidates. Earlier ABI/bytecode false positives were rejected before acceptance and converted to permanent regressions. No private/global absence inference is allowed;
13. **COMPLETE BOUNDED ALLOCATION-SOURCE PROVENANCE:** `xone_xnt_allocation_source_provenance/v1` accepted via #619 / PR #620. Final run #6 covered 3/3 repositories, 41 provenance-shaped files, 3/3 release queries and 3/3 official X1 targets. It retained 10 clean non-XONE `x1_program_schema` architecture analogues and found 0 qualifying XONE allocation-source candidates / 0 exact-XONE-bound sources. Earlier false-positive classes were rejected and converted into permanent regressions. No private/global absence inference is allowed;
14. **COMPLETE LEAD-DRIVEN PRIMARY ARTIFACT RESOLUTION:** `xone_xnt_primary_allocation_artifact_resolution/v1` accepted via #622 / PR #623. Run #3 proves the intentional `NO_LEAD` idle state with zero network-client imports / zero discovery requests; deterministic prior-boundary regressions and Liquidity Scout Tests #1838 passed. CMIS can classify an already-retrieved artifact as NO_LEAD / REJECTED / CANDIDATE / RESOLVED_FOR_HANDOFF and route only reproducible exact-XONE evidence into a stronger verifier;
15. **WAIT FOR AN EXACT PRIMARY LEAD:** registry/export, holder CSV/JSON, authoritative API/Merkle pointer, content-addressed artifact, exact deployed X1 program/account schema explicitly tied to XONE, or externally supplied primary evidence. Do not restart the exhausted broad corpus automatically;
16. when an authoritative exact snapshot block is resolved, run the accepted full Ethereum ledger reconstruction from XONE creation through that block, require historical `totalSupply()` and deterministic `balanceOf()` checks, and require two-RPC registry-digest agreement;
17. separately prove the **snapshot → XNT allocation binding**: ratio/formula, exclusions/minimums, Ethereum→X1 wallet mapping, claim/allocation record, and whether the allocation is already fixed;
18. separately prove XNT issuance/vesting/unlock semantics for **XONE-derived** allocations, including whether October 6 applies;
19. add deterministic Ethereum -> X1 correlation only after both exact sides are independently verified;
20. add persistent claim-ledger storage and supersession metadata;
21. only then consider any public CMIS or X1 Scout promotion.
