# X1 Provider Gap Register

Status date: **2026-08-18**

This register tracks capability gaps beneath CMIS for the X1 Provider. It is a planning and verification document, not a source of live market facts.

Architecture boundary:

```text
Roberta
  -> X1 Scout
    -> CMIS
      -> X1 Provider
        -> X1 RPC / X1.Ninja / XDEX / other verified X1 sources
```

Provider-specific endpoint discovery, contract verification, and transport logic belong in this repository. Roberta and X1 Scout must not call or reinterpret provider endpoints directly.

## Status vocabulary

- **VERIFIED** — the capability has a current deterministic implementation or an official/public contract that has been validated sufficiently for the stated scope.
- **PARTIAL** — useful capability exists, but coverage, redundancy, semantics, or CMIS promotion is incomplete.
- **CANDIDATE** — a provider advertises or demonstrates the capability, but CMIS has not contract-tested it enough for production use.
- **BLOCKED** — implementation exists or an endpoint is known, but a required live contract/semantic assumption is unresolved.
- **MISSING** — no production-ready provider path is currently available.

A public webpage, release note, UI, advertised endpoint, source label, or candidate hostname is evidence for investigation only. It does not become an authoritative CMIS source until deterministic provenance, request/response contracts, failure semantics, and the fact-specific promotion requirements are verified.

## Current accepted trust checkpoint

The accepted CMIS/X1 trust layer now includes deterministic evidence/provenance, content-addressed evidence storage and exact lookup, explicit Roberta/X1 Scout evidence eligibility, pool-specific reserve identity/scope verification, holder concentration/enumeration semantic gates, bounded SSE handshake classification, chain-first activity-window evidence, and historical trust contracts for secondary-RPC response classification, explicit-request-context block comparison, sanitized comparison evidence, and fail-closed retention sample aggregation.

PRs #161 and #162 strengthened the historical boundary:

- `getBlock` observations do not infer the requested block slot from `parentSlot + 1`; skipped slots make that inference unsafe;
- different source labels do not prove source independence; independence must be explicitly established;
- optional block-height evidence is compared only when both observations provide it;
- sparse historical samples may record observed agreement/conflict across selected slots but never prove continuous coverage, retention, finality equivalence, archival completeness, or CMIS promotion;
- retention aggregation revalidates evidence schema, subject/slot identity, source identities, quality/status invariants, compared fields, conflicts, timestamps, and non-promotion flags before accepting a sample.

PR #143 adds a fail-closed Warp Bridge provenance gate:

- an accepted provenance proof must bind to the exact candidate HTTPS read URL;
- host ownership, an allowed proof label, third-party extension metadata, or a proof for a different URL is insufficient;
- endpoint semantics and CMIS promotion remain false until a later read-only contract probe succeeds.

These accepted mechanisms do **not** promote unresolved provider semantics. In particular:

- the live XENCAT/XNT reserve proof is pool-specific and must not be generalized;
- holder totals remain unavailable until counted-entity semantics and coverage are independently proven;
- X1.Ninja SSE support remains access-unclassified until a manual live handshake is run;
- historical comparison/sample contracts do not prove that any secondary provider has sufficient retention, finality, reconnect/backfill behavior, or archival completeness;
- no real Warp Bridge machine-readable endpoint has been provenance-approved merely because the provenance gate exists.

## Capability register

| ID | Capability | Status | Current evidence / implementation | Promotion requirement / next action |
|---|---|---|---|---|
| X1-RPC-01 | Core X1 RPC coverage | VERIFIED | Existing X1 RPC provider is in use. Official X1 documentation also supports a self-hosted read-only node with full RPC. | Preserve provider tests and explicit RPC provenance. |
| X1-RPC-02 | Historical transaction RPC | PARTIAL | Deterministic secondary `getHealth`/`getSlot`/`getBlock` response classification, explicit-request-context historical block comparison, sanitized evidence, and fail-closed retention sample aggregation are accepted. These contracts are non-promotional. | Run live/captured observations against a chosen secondary/self-hosted source and verify retention depth, finality semantics, reconnect/backfill behavior, errors, and historical method coverage before claiming archival completeness. |
| X1-RPC-03 | RPC redundancy / failover | PARTIAL | Official X1 RPC is available. Self-hosted X1 read-only node and X1Scroll have separately documented candidate roles. Historical comparison now requires explicit source-independence verification rather than treating different labels as independent. | Verify actual provider independence plus auth, methods, retention, finality, latency, quotas, errors, and failover behavior before promotion. |
| X1-IDX-01 | General transaction / wallet indexer | PARTIAL | X1.Ninja demonstrates deep XDEX indexing, but a complete general wallet-indexer contract is not established for CMIS. | Discover/test machine-readable wallet/indexer contracts; do not infer from UI/release notes. |
| X1-DEX-01 | Pool catalog / liquidity / volume | VERIFIED | X1.Ninja/XDEX catalog path is used by CMIS; direct XDEX public pool transport also exists as an independent provider-native path. | Maintain asset-wide aggregation, pool deduplication, timestamps, and source traceability. |
| X1-DEX-02 | Pool detail / reserves | VERIFIED (POOL-SPECIFIC) | The fail-closed identity/semantic/evidence chain is accepted. Live XENCAT/XNT evidence proved exact token-unit agreement for pool `6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry`. | Do not generalize this proof. New pools require their own identity/unit/scope evidence. |
| X1-DEX-03 | Holder data | PARTIAL | Fail-closed concentration/enumeration and observational-comparison code is accepted. | Run same-run live observational probe and obtain independent counted-entity/coverage proof. Token accounts must not be relabeled as wallets or beneficial owners. |
| X1-HIST-01 | X1.Ninja trade history | PARTIAL | `/v1/trades/{address}` structure/transport coverage is accepted. | Verify type, units, finality, pagination/range, duplicates, ordering, and stale behavior before semantic promotion. |
| X1-HIST-02 | X1.Ninja OHLCV | PARTIAL | Deterministic contract tests and opt-in live probing are accepted. | Verify timestamp, pair direction, quote unit, interval/range/gap semantics before CMIS history promotion. |
| X1-HIST-03 | Direct XDEX chart/history | BLOCKED | Read-only transport exists, but exact live pair/response semantics remain gated. | Verify timestamp, price/quote units, pair direction, interval/range, and exact current pool identity. |
| X1-QUOTE-01 | Direct XDEX read-only quote | BLOCKED | Quote transport exists, but live token-supply/native-XNT handling remains unresolved. | Verify an exact current non-XNT pair, amounts, rate, route, fees, freshness and impact semantics. |
| X1-STREAM-01 | X1.Ninja real-time trades | PARTIAL | Bounded SSE handshake classifier/workflow is accepted. No event-body consumption is required for access classification. | Run manual live handshake to classify current access. Only after access is proven should reconnect/order/backfill semantics be tested. |
| X1-STREAM-02 | General chain real-time stream | PARTIAL | Official self-hosted X1 node supports block PubSub; X1Scroll remains an independent candidate. | Contract-test commitment/finality, reconnect, ordering, backfill, retention and gap behavior. |
| X1-XCHECK-01 | Same-fact independent verification | VERIFIED (FRAMEWORK) | Deterministic evidence/provenance, agreement/conflict/insufficient-evidence rules, data-quality gating and exact evidence lookup are accepted. Historical comparison now fails closed unless source independence is explicitly verified. | Continue fact-specific verification recipes; framework availability is not proof of any individual market fact or source independence. |
| X1-BRIDGE-01 | Bridge operational state | MISSING | Exact-URL provenance gating is accepted, but no actual Warp Bridge machine-readable read URL has yet been provenance-approved and contract-tested. | Obtain an exact URL from X1-owned documentation/artifacts, sanitized official-app network observation, or independently verifiable on-chain configuration; then run a bounded read-only contract probe. Guessed paths are forbidden. |
| X1-BRIDGE-02 | Supported bridged assets / representations | PARTIAL | Canonical representation modeling exists; UI evidence shows chain-side representations. The exact-URL provenance gate is available for a future machine-readable source. | Verify exact bridge configuration source, chain/address identity, decimals and route support. |
| X1-BRIDGE-03 | Bridge fees / route capacity | MISSING | UI exposes route/fee/network-fee concepts; no verified machine-readable contract exists. | Prove exact source provenance first, then verify units, freshness, capacity meaning and fee components. |
| X1-BRIDGE-04 | Bridge transfer state / history | MISSING | UI exposes history/status concepts; X1 Prism remains only a candidate cross-check. | Identify an authoritative provenance-approved read-only lifecycle source and verify identifiers/finality/retry semantics. |
| X1-BRIDGE-05 | Guardian set / guardian health | PARTIAL | UI evidence exposes guardian concepts only. | Identify the exact underlying source and verify provenance, identity, quorum/threshold and status freshness. |
| X1-BRIDGE-06 | Bridge-flow / TVL independent verification | CANDIDATE | X1 Prism exposes Today In/Out/Net/TVL fields, but provenance/API contract is unproven. | Keep independent-only until contract and provenance are verified. |
| X1-ALT-01 | X1Scroll archival RPC / streaming | CANDIDATE | Separate redundancy role is documented; provider claims remain unverified. | Validate auth, methods, actual independence, retention, finality, reconnect, quotas and deterministic errors. |
| X1-ALT-02 | FortiBlox explorer / RPC ecosystem | CANDIDATE | Explorer/analytics and RPC-related infrastructure are documented with mixed maturity. | Verify each endpoint independently and exclude planned functionality from capability claims. |

## CMIS promotion rules

Before any PARTIAL, CANDIDATE, BLOCKED, or MISSING capability is promoted to production CMIS logic:

1. Record exact provider/source, endpoint or account contract, observed-at time, authentication requirements, rate limits/quotas, and raw response shape.
2. Fail closed on malformed success envelopes, missing required fields, stale data, undocumented units, or ambiguous identities.
3. Treat chain + verified address/mint as authoritative for token representations; symbols and names remain metadata unless a canonical registry mapping explicitly says otherwise.
4. Preserve canonical asset identity separately from provider/DEX/bridge representations.
5. Record completeness and uncertainty; never replace missing values with zero.
6. Add deterministic unit/contract tests before CMIS promotion.
7. Add an opt-in live verification test where the capability is freshness-sensitive or provider-contract dependent.
8. Preserve source role and timestamp in the CMIS envelope.
9. For same-fact cross-checks, verify actual source independence and define deterministic disagreement behavior instead of averaging incompatible facts.
10. Do not infer historical slot identity from response fields that do not actually carry the requested slot, and do not promote sparse observations into retention/archival claims.

## Immediate work order from the current checkpoint

1. **Manual SSE access classification** — run the accepted bounded `/v1/stream/trades` handshake probe; consume no event bodies and do not infer stream semantics from access alone.
2. **Holder observational evidence** — run the accepted same-run holder observation and retain semantic/coverage uncertainty unless independently proven.
3. **Warp Bridge source discovery** — obtain one real exact machine-readable read URL with accepted provenance. The provenance gate is merged, but it does not discover or validate an endpoint by itself. After provenance succeeds, build a bounded read-only response-contract probe.
4. **Historical redundancy live evidence** — select a secondary/self-hosted source, prove source independence, capture bounded `getHealth`/`getSlot`/`getBlock` observations across explicit requested slots, and test retention/finality/reconnect/backfill behavior. The merged #161/#162 contracts validate evidence; they do not promote a provider on their own.
5. **Independent bridge cross-check** — evaluate X1 Prism only after its own machine-readable provenance/contract is verified.
6. **Only after these trust gaps** continue broader X1 provider intelligence work; do not use Phase 11 execution work to bypass unresolved evidence gaps.

## Source registry

Research basis maintained from 2026-08-16 through 2026-08-18:

- X1.Ninja Developer API — `https://x1.ninja/developers`
- X1.Ninja Release Notes — `https://x1.ninja/release-notes`
- Official X1 read-only node documentation — `https://docs.x1.xyz/validating/create-a-read-only-node`
- X1Scroll — `https://x1scroll.io/`
- Official Warp Bridge — `https://app.bridge.x1.xyz/`
- X1 Prism — `https://x1prism.com/`
- FortiBlox Explorer docs — `https://docs.fortiblox.com/docs/explorer/intro`
- FortiBlox RPC Proxy docs — `https://docs.fortiblox.com/docs/nexus/security/rpc-proxy`
- Existing direct-XDEX contract record — `docs/XDEX_READ_ONLY_PROVIDER.md`
- Historical redundancy evaluation — `docs/X1_HISTORY_STREAM_REDUNDANCY_EVALUATION.md`
- Warp Bridge source-discovery boundary — `docs/X1_WARP_BRIDGE_SOURCE_DISCOVERY.md`

Research boundary: this register records capability evidence and integration status. It does not certify provider uptime, current endpoint access, response accuracy, source independence, retention depth, archival completeness, or contractual stability unless the specific row is explicitly marked verified for that scope.
