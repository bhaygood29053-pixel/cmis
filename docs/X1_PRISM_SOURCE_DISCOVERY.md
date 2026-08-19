# X1 Prism source discovery and verification boundary

Research date: **2026-08-18**

## Purpose

Evaluate X1 Prism only as a possible independent read-only cross-check for X1 Warp Bridge flow and TVL evidence.

This record does **not** promote X1 Prism into the X1 Provider and does not certify any current bridge metric.

## Current classification

```text
source = X1 Prism
role = candidate independent bridge cross-check
status = CANDIDATE / UNVERIFIED
machine_readable_contract_verified = false
source_independence_verified = false
bridge_fact_semantics_verified = false
freshness_verified = false
cmis_promotable = false
```

## Public surface observed

The current public X1 Prism site describes itself as a community-built X1 portfolio and analytics dashboard. Its X1 Bridge section is labeled for the Warp Bridge between Solana and X1 and exposes these UI fields:

- `Today In`
- `Today Out`
- `Net`
- `TVL`

In the current public search-visible observation, those four fields rendered as placeholders (`—`) rather than verified numerical values.

That proves only that the UI has named bridge-flow/TVL concepts. It does **not** establish:

- an exact API endpoint;
- an on-chain account or program used to derive the values;
- a stable machine-readable response contract;
- the calculation formula for any metric;
- the time-zone/reset semantics of `Today`;
- the asset scope included in `TVL`;
- the USD pricing source used for valuation;
- transfer inclusion/exclusion rules;
- source independence from the official Warp Bridge application, XDEX, X1.Ninja, or another indexer;
- current bridge health, capacity, supported routes, or transfer status.

## Provenance search result

The current research pass found the public X1 Prism application but did **not** find public API documentation, a clearly attributable public source repository, or another stable machine-readable contract that explains the bridge metrics.

Public search indexes also surfaced third-party social mirrors containing a launch-style statement attributed to `@Shaka_Vibes` about X1 Prism and XDEX sourcing. However, this research pass did **not** recover the original post URL/status identifier or another first-party artifact that makes that statement reproducibly attributable.

CMIS therefore excludes that social-mirror statement from accepted provenance evidence. It is **not** used to conclude that Prism depends on XDEX, and it is **not** used to make any bridge-metric source claim.

The accepted conclusion requires no such social claim:

```text
bridge-metric-specific source = unverified
source independence from XDEX = not established
source independence from Warp Bridge upstream = not established
```

X1 Prism cannot currently be treated as an independent verifier merely because it displays values that resemble bridge facts. Independence remains unverified until the exact upstream lineage for the specific bridge metric is established.

## Independence rule

For CMIS same-fact verification, a different website or source label is not evidence of source independence.

Before X1 Prism may participate in an independent bridge cross-check, CMIS must determine whether its bridge values are derived independently from the source being checked. If Prism reads the official Warp Bridge API, reproduces the same upstream cache, or derives the values from the same XDEX/indexer evidence, numerical agreement would not count as independent corroboration.

A future independence proof must identify both sides of the comparison:

1. the exact primary bridge fact source being checked;
2. the exact X1 Prism bridge-metric source;
3. the upstream dependencies for each;
4. evidence that the two observations do not collapse to the same provider/cache/indexer/account calculation.

## Required contract before integration

Do not build a production adapter until an exact read-only machine source is discovered and provenance is established.

For each candidate source, verify:

1. **Exact contract** — exact HTTPS endpoint, RPC method, account/program, or other machine-readable source.
2. **Provenance** — evidence that X1 Prism actually uses that exact source for the relevant bridge metric.
3. **Metric identity** — exact meaning of `Today In`, `Today Out`, `Net`, and `TVL`.
4. **Window semantics** — start/end time, timezone, reset behavior, and whether partial-day values are expected.
5. **Asset scope** — which bridged assets and representations are included or excluded.
6. **Direction semantics** — what counts as inbound vs outbound across Solana and X1.
7. **Transfer lifecycle rules** — pending, finalized, failed, refunded, duplicated, retried, or reversed transfers.
8. **Valuation semantics** — raw-token versus USD values, price source, price timestamp, decimals, and rounding.
9. **Freshness** — source timestamp or block/slot context and stale-data behavior.
10. **Source independence** — demonstrate that the observation is not simply copied from or derived through the primary bridge source being verified.
11. **Failure semantics** — malformed success envelopes, partial data, rate limits, provider errors, and unavailable values must fail closed.
12. **Deterministic tests** — fixture/contract tests before any CMIS promotion, plus an opt-in live read-only probe where freshness matters.

## Safe scope

Permitted future work is read-only discovery and observation only.

Do not use X1 Prism research to:

- prepare bridge transactions;
- connect or control wallets;
- sign messages or transactions;
- broadcast transfers;
- move assets;
- infer bridge safety from UI availability;
- infer source independence from domain ownership or branding;
- promote missing values to zero.

## CMIS conclusion

X1 Prism remains useful as a **candidate** bridge-flow/TVL research surface because it visibly exposes relevant analytical fields. However, the current reproducible evidence does not establish a stable machine-readable contract or independent data provenance.

This is not evidence that Prism is unsafe or inaccurate. It is an evidence-role decision: **a source cannot be used as independent corroboration until its upstream lineage is known to be independent for the specific fact being compared.**

Until both the bridge-specific contract and actual upstream independence are proven, the accepted boundary remains:

```text
X1-BRIDGE-06 = CANDIDATE
independent verification = unavailable
CMIS promotion = false
```

The next valid engineering step is to identify the exact read-only source used for the four bridge metrics and map its upstream dependencies. Only then should CMIS decide whether an X1 Prism provider adapter is useful at all.

## Research sources

- X1 Prism public application: `https://x1prism.com/`
- third-party indexed social-mirror observation: excluded from accepted provenance because the original post URL/status identifier was not recovered
- official Warp Bridge surface for comparison/context: `https://app.bridge.x1.xyz/`
- current CMIS gap register: `docs/X1_PROVIDER_GAP_REGISTER.md`
- Warp Bridge discovery boundary: `docs/X1_WARP_BRIDGE_SOURCE_DISCOVERY.md`
