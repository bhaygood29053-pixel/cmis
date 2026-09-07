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

The source registry remains intentionally narrow. The exact Ethereum mainnet XONE identity is accepted under `ethereum_xone_identity/v1`, bounded canonical ERC-20 event observation under `ethereum_xone_event_observer/v1`, burn/redeemer semantics under `ethereum_xone_migration_sink_semantics/v1`, exact-address Ethereum candidate extraction under `xone_xnt_conversion_candidate_discovery/v1`, independent X1-side XNT rule/account discovery under `x1_xnt_distribution_mechanism_discovery/v1`, and exact X1-side binding discovery under `xone_xnt_x1_binding_discovery/v1`. The latest bounded binding run had 4/4 official X1 targets and 13/13 ranked X1 Report pages available but produced 0 explicit XONE/XNT conversion claims and therefore 0 exact X1 binding candidates. That is scoped corpus evidence only; it does not identify or disprove an XONE→XNT mechanism.

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
7. broaden authoritative/public **XONE-specific** source coverage and provenance qualification to find an exact converter, migration, claim, allocation, vesting, or X1 program/account reference;
8. qualify any newly discovered exact Ethereum or X1 identifier directly on-chain before semantic role binding;
9. add deterministic Ethereum -> X1 correlation only after both exact sides are independently verified;
10. add persistent claim-ledger storage and supersession metadata;
11. only then consider any public CMIS or X1 Scout promotion.
