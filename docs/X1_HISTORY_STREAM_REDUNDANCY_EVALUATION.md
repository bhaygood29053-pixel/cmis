# X1 history and streaming redundancy evaluation

Research date: **2026-08-17**

Refresh note: this document is carried forward as a research/architecture baseline on the current CMIS `main`. Provider capability claims remain unverified until the deterministic acceptance tests below are performed; this refresh does not promote either candidate into production CMIS truth.

## Purpose

Evaluate the next X1 Provider redundancy layer without promoting advertised capabilities into CMIS before deterministic contract tests exist.

This document compares two different infrastructure roles:

1. an operator-controlled **official X1 read-only node**; and
2. **X1Scroll** as a third-party archival / streaming candidate.

The conclusion is architectural, not an uptime, latency, retention, or accuracy certification.

## Source classification

### Official X1 read-only node

Classification: **OFFICIAL DOCUMENTATION / operator-controlled provider candidate**.

The current X1 read-only-node documentation shows a Tachyon validator process configured with:

- `--full-rpc-api`;
- `--enable-rpc-transaction-history`;
- `--enable-extended-tx-metadata-storage`;
- `--rpc-pubsub-enable-block-subscription`.

The published sample also uses `--limit-ledger-size 50000000`.

Engineering interpretation:

- the node can provide a controlled full-RPC/history/metadata/Block-PubSub source;
- retention is still an operator/configuration/storage concern;
- the documented sample should **not** be relabeled as guaranteed unpruned archival history;
- a CMIS deployment would need an explicit retention/storage policy and empirical oldest-slot/history tests.

Primary source:

`https://docs.x1.xyz/validating/create-a-read-only-node`

Supporting official mainnet connection guide:

`https://docs.x1.xyz/validating/connect-validator-to-x1-mainnet`

### X1Scroll

Classification: **THIRD-PARTY PROVIDER CANDIDATE — contract testing required**.

The current X1Scroll site advertises:

- archival RPC with growing history and no pruning;
- historical queries;
- WebSocket support / streaming on paid tiers;
- a Yellowstone gRPC / Geyser endpoint at `grpc.x1scroll.io:10000`;
- token/API-key based access and plan-specific quotas.

Those are provider claims, not CMIS-verified facts about retention completeness, finality, latency, uptime, reconnect behavior, or dropped-event handling.

Primary provider source:

`https://x1scroll.io/`

## Architectural comparison

| Dimension | Self-hosted X1 read-only node | X1Scroll candidate |
|---|---|---|
| Control | Operator controlled | Third party controlled |
| Source role | Provider-native / controlled X1 RPC | Independent third-party redundancy |
| RPC/history | Official configuration supports full RPC + transaction history | Advertises archival RPC + historical queries |
| Retention | Must be configured/measured; sample uses bounded ledger size | Advertises no pruning; must verify empirically |
| Streaming | Official config supports block PubSub; other subscriptions require contract testing | Advertises WebSocket/streaming and Yellowstone gRPC |
| Authentication | Local/operator network policy | Provider key/token |
| Quotas | Operator capacity | Provider plan / quota dependent |
| Failure independence | Depends on operator/X1 network infrastructure | Separate third-party operational domain |
| CMIS status now | Candidate, not production-promoted by this evaluation | Candidate, not production-promoted by this evaluation |

## Recommended provider roles

The two sources should not be treated as interchangeable.

### Operator-controlled read-only node

Target role:

- controlled X1 RPC history source;
- deterministic transaction/block verification source;
- controlled PubSub source;
- future provider-native fallback when public RPC/indexer behavior is insufficient;
- reproducible retention and finality measurements under CMIS control.

### X1Scroll

Target role:

- independent history cross-check;
- backup RPC candidate;
- independent WebSocket / Geyser streaming candidate;
- outage / disagreement redundancy against X1.Ninja, public X1 RPC, or a self-hosted node.

Do **not** make X1Scroll the sole source of historical or streaming truth without contract evidence.

## Deterministic acceptance work

### Self-hosted node acceptance tests

Before CMIS can rely on a self-hosted X1 node, record and test:

1. exact Tachyon/X1 software version and startup configuration;
2. `getHealth`, `getSlot`, `getBlock`, `getTransaction`, signature-history, and other required RPC contracts;
3. finalized/confirmed commitment behavior;
4. oldest retained slot / oldest retrievable transaction at repeated checkpoints;
5. ledger growth and pruning behavior under the chosen `--limit-ledger-size` / storage policy;
6. restart/recovery behavior;
7. block-subscription reconnect behavior;
8. duplicate-event handling;
9. backfill strategy after disconnect;
10. dropped-event detection;
11. local clock / observed-at provenance;
12. rate/capacity behavior under bounded read-only CMIS load.

### X1Scroll acceptance tests

Before CMIS can rely on X1Scroll, verify:

1. authentication format and secret handling;
2. supported RPC methods and exact response semantics;
3. historical-range depth with known old blocks/transactions;
4. pruning/retention behavior over time rather than relying on the phrase “no pruning”;
5. commitment/finality semantics;
6. WebSocket subscription contracts;
7. Yellowstone gRPC authentication and supported event types;
8. reconnect/resume behavior;
9. duplicate-event behavior;
10. backfill after disconnect;
11. dropped-event detection or sequence-gap evidence;
12. request/stream quotas and deterministic rate-limit errors;
13. latency measurements using recorded methodology;
14. provider outages / degraded-mode behavior;
15. same-fact disagreement handling against official X1 RPC or a self-hosted node.

## CMIS promotion boundary

No source is promoted by this document.

A future history/streaming provider should expose:

- source identity;
- source role;
- endpoint/provider version where available;
- observed-at time;
- block/slot and commitment/finality;
- retention/range coverage;
- completeness and gap indicators;
- reconnect/backfill provenance;
- warnings/errors;
- deterministic data-quality state.

CMIS must not average or silently reconcile incompatible history/stream observations.

## Directional decision

The preferred redundancy architecture is **two-role**, not winner-take-all:

```text
X1 Provider
├── official/public X1 RPC (existing live source)
├── operator-controlled X1 read-only node (controlled history / verification)
└── X1Scroll (independent archival / streaming cross-check candidate)
```

This preserves source independence while giving CMIS a path toward controlled historical retention.

The next engineering step is **contract testing**, not provider promotion or infrastructure purchase/deployment.
