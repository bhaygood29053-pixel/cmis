# X1 Provider Source Research

Research date: **2026-08-16**

This document records public-source findings relevant to current X1 Provider gaps beneath CMIS. It supports `docs/X1_PROVIDER_GAP_REGISTER.md` and future deterministic provider integration work.

A public webpage, UI, release note, or advertised feature is not automatically a CMIS-authoritative source. Machine-readable contracts must be tested before production promotion.

## Research classifications

- **VERIFIED PUBLIC DOCUMENTATION** — capability is explicitly documented by a current public source.
- **SUPPORTING IMPLEMENTATION EVIDENCE** — public evidence suggests infrastructure exists, but the CMIS-facing contract still requires direct verification.
- **CANDIDATE** — a third party advertises or exposes the capability but CMIS has not contract-tested it.
- **UNVERIFIED ACCESS** — an endpoint or feature is documented, but current tier/access or response semantics still require testing.

## Executive findings

| Capability | Research status | Finding |
|---|---|---|
| RPC / node history | Available | Official X1 documentation supports full RPC, transaction history, extended transaction metadata, and block PubSub on a self-hosted read-only node. |
| General indexing | Partial | X1.Ninja publicly demonstrates deep XDEX trade/wallet indexing, but the published API surface does not yet establish a complete general wallet-indexer contract for CMIS. |
| DEX market data | Available | X1.Ninja documents pools, pool detail, trades, and OHLCV endpoints. Existing direct XDEX transport remains useful as an independent/provider-native source. |
| Historical market data | Available candidate | X1.Ninja exposes OHLCV and trade history. Both require deterministic contract testing before CMIS promotion. |
| Real-time streams | Available candidate | X1.Ninja documents an SSE trade stream; X1Scroll advertises Yellowstone gRPC/Geyser. Access and semantics require live verification. |
| Independent verification | Improving | Official X1 RPC, X1.Ninja, direct XDEX, self-hosted nodes, X1Scroll, and FortiBlox create potential redundancy, but same-fact deterministic cross-checks are not yet fully implemented. |
| Bridge Intelligence | Clearest remaining X1 gap | Official Warp Bridge and X1 Prism expose bridge-related UI/status metrics, but no stable documented public read-only bridge API was established by this research. |
| Oracle V2 price evidence | Candidate (supplemental research 2026-08-26) | Public repository evidence describes a multi-source external price feed, OpenBao-signed relays, and an X1 Oracle Vault. Current deployed program/state identity and live slot semantics remain unverified by CMIS. |

## X1.Ninja Developer API

Classification: **VERIFIED PUBLIC DOCUMENTATION / integration candidate**.

Public documentation describes a base URL, Bearer authentication, quotas/rate limits, and machine-readable endpoints including:

- `/v1/pools` — pool list with price, volume, liquidity, and market-cap fields;
- `/v1/pools/{address}` — pool detail including reserves, token metadata, and holders;
- `/v1/trades/{address}` — trade history for a pool, including buys, sells, and LP events;
- `/v1/ohlcv/{address}` — OHLCV candles with 1m, 5m, 15m, 1h, 4h, and 1D timeframes;
- `/v1/stream/trades` — live Server-Sent Events trade stream.

Access note: the public page lists pools/trades/OHLCV in the free tier, while the live stream is listed under a Pro tier marked `SOON`. CMIS must verify current access rather than assuming the stream is production-available.

Source: `https://x1.ninja/developers`

## X1.Ninja Release Notes

Classification: **SUPPORTING IMPLEMENTATION EVIDENCE**.

Release notes describe wallet trade history, wallet metrics, holder data, a global SSE trade stream, Geyser-driven updates, real-time pool/trade processing, and on-chain reserve verification.

These notes support provider discovery but do not replace direct request/response contract tests.

Source: `https://x1.ninja/release-notes`

## Official X1 read-only node

Classification: **VERIFIED OFFICIAL X1 DOCUMENTATION**.

Official instructions show that a self-hosted X1 node can run with:

```text
--full-rpc-api
--enable-rpc-transaction-history
--enable-extended-tx-metadata-storage
--rpc-pubsub-enable-block-subscription
```

Engineering implication: the X1 data stack does not have to depend exclusively on third-party RPC/indexer providers. A dedicated read-only node is a viable future source for controlled RPC history and subscription data.

Source: `https://docs.x1.xyz/validating/create-a-read-only-node`

## X1Scroll

Classification: **THIRD-PARTY CANDIDATE — MUST CONTRACT-TEST**.

X1Scroll advertises archival RPC, historical queries, WebSocket/streaming support, and a Yellowstone gRPC/Geyser endpoint at `grpc.x1scroll.io:10000`.

Potential use beneath X1 Provider:

- archive/history provider;
- backup RPC;
- real-time Geyser provider.

Required checks include authentication, supported RPC methods, retention depth, commitment/finality, reconnect behavior, latency, quotas, and errors.

Source: `https://x1scroll.io/`

## Official Warp Bridge

Classification: **OFFICIAL USER-FACING BRIDGE SURFACE; PUBLIC READ-ONLY API NOT VERIFIED**.

The Warp Bridge is an official Solana-to-X1 cross-chain bridge. Public UI evidence shows bridge/history/info/status concepts and structured fields for route/fees/network fees/status.

A supplied 2026-08-16 screenshot also visibly shows:

- separate Solana and X1 chain-status cards;
- bridged-token entries with chain-side representations;
- bridge transfer/activity summary information;
- a guardian set with chain/public-key/status fields.

Those observations establish that the user-facing application has access to structured bridge information. They do **not** establish a stable public API or authoritative CMIS data source.

The current provider-discovery task is to identify the machine-readable source used by the UI and then contract-test it. Possible mechanisms include HTTP APIs, RPC/on-chain accounts, embedded configuration, or streaming transports; none should be assumed before observation.

Do not treat a UI `Live`, `Healthy`, `Offline`, or similar status label from a prior observation as a current bridge-health fact.

Source: `https://app.bridge.x1.xyz/`

## X1 Prism

Classification: **THIRD-PARTY BRIDGE VERIFICATION CANDIDATE**.

X1 Prism exposes an X1 Warp Bridge section with fields for Today In, Today Out, Net, and TVL. The research observation returned placeholder values and did not establish a documented public API or data provenance.

Use only as a candidate independent cross-check until its machine-readable contract and source origin are proven.

Source: `https://x1prism.com/`

## FortiBlox

Classification: **THIRD-PARTY CANDIDATE / MIXED MATURITY**.

FortiBlox documentation advertises an X1 Explorer with real-time blockchain data, transaction history, analytics, and developer integrations. RPC documentation references FortiBlox RPC infrastructure, while some RPC-proxy functionality is described as planned/coming.

Every endpoint must therefore be verified individually, with live capabilities kept separate from roadmap claims.

Sources:

- `https://docs.fortiblox.com/docs/explorer/intro`
- `https://docs.fortiblox.com/docs/nexus/security/rpc-proxy`

## Oracle V2 — supplemental research 2026-08-26

Classification: **PUBLIC IMPLEMENTATION EVIDENCE / X1 READ-ONLY PROVIDER CANDIDATE**.

Repository: `https://github.com/jacklevin74/oracle-v2`

Pinned research commit: `97177f772689e44ca4eed9bb95be32ffdf0c5e66`

A review of the public repository at that commit found:

- a Python price-feed server collecting Pyth plus CEX observations from Coinbase, Kraken, MEXC, and KuCoin in the active aggregation path;
- weighted-median aggregation with Pyth weighted `2.0` and each reviewed active CEX source weighted `1.0`;
- five TypeScript relay clients consuming the common aggregated feed;
- OpenBao Transit Ed25519 signing;
- X1 submission using an Ed25519 verification pre-instruction plus the Oracle Vault instruction;
- an Anchor/Solana-compatible Oracle Vault storing five relay slots for each of six on-chain assets: BTC, ETH, SOL, HYPE, ZEC, and FARTCOIN;
- repository-declared X1 program ID `9mPmjK8NxJadYDiHiYAQH4WFCnKJr7ZV8ria63ZkMtv2`;
- repository-declared state PDA `8XZBqbKhFXHqNGzxV3Tt6gEs9r8ZrNghsRg7zBwLMGJf`.

The reviewed price-feed also includes Pyth mappings for TSLA, NVDA, MSTR, GOLD, and SILVER. Those feed-server mappings must not be interpreted as on-chain Oracle Vault asset support; the reviewed on-chain program stores only six assets.

The repository claims X1 mainnet deployment, but this research pass did **not** independently verify through X1 RPC:

- current program account identity/executable state;
- state-account owner;
- PDA derivation against the deployed program;
- deployed account layout;
- current relay-slot prices/timestamps/freshness;
- current oracle signing-key identity;
- current correctness or availability of the upstream feed.

CMIS architecture implication: if accepted later, Oracle V2 should be consumed as read-only on-chain evidence through the X1 Provider/X1 RPC boundary. CMIS should not run OpenBao, hold relay keys, submit oracle prices, or add a signing/broadcast path merely to consume the source.

Evidence-quality warning: the five relay clients consume a common aggregated feed in the reviewed implementation. Five relay slots therefore do not establish five independent market-price sources. Relay redundancy, underlying source diversity, same-fact agreement, and actual source independence must remain separate proof dimensions.

Detailed research and acceptance requirements: `docs/X1_ORACLE_V2_SOURCE_RESEARCH.md`

Tracking issue: **#272**.

## Required verification before CMIS promotion

For any new provider/source, record:

- exact source and endpoint/account contract;
- `observed_at` time;
- authentication requirements;
- rate limits/quotas;
- raw provider response;
- required fields and units;
- freshness/staleness behavior;
- deterministic error/failure behavior.

Fail closed on malformed success envelopes, missing fields, undocumented units, stale data, or ambiguous token identities.

### Asset identity

Use verified address/mint identity for token representations. Symbols and names are metadata. Canonical asset identity remains separate from provider/DEX/bridge representations through the CMIS asset registry.

### OHLCV

Verify timestamp units, pair direction, quote currency/unit, interval semantics, requested-range coverage, gaps, stale/interpolated behavior, and provenance.

### Trades

Verify side classification, token amounts/decimals, USD-value source, LP-event semantics, transaction signature, finality, pagination/range, duplicates, and ordering.

### Reserves / holders

Cross-check against X1 RPC/on-chain accounts where possible before treating reported values as independently verified totals.

### SSE / Geyser / PubSub

Test reconnect behavior, duplicate events, ordering, commitment/finality, backfill behavior, dropped-event detection, and stream freshness.

### Bridge Intelligence

Verify separately:

- bridge operational state;
- supported assets;
- canonical asset plus source/destination representations;
- route support and capacity;
- fees and units;
- transfer lifecycle/state;
- source/destination finality;
- guardian identity, quorum/threshold, and health freshness;
- usable post-bridge XDEX liquidity where economically relevant.

## Project ownership

Primary project: **liquidity-scout**.

This repository owns X1 Provider source candidates, endpoint contracts, bridge-intelligence discovery, transport adapters, and deterministic provider tests.

Roberta should know summarized capability status, but provider endpoint details should not be duplicated upward. The architectural boundary remains:

```text
Roberta -> X1 Scout -> CMIS -> X1 Provider
```

## Work order

1. Maintain `docs/X1_PROVIDER_GAP_REGISTER.md` as the capability baseline.
2. Contract-test X1.Ninja `/v1/trades/{address}`.
3. Contract-test X1.Ninja `/v1/ohlcv/{address}`.
4. Cross-check X1.Ninja reserves/holders against X1 RPC evidence.
5. Probe X1.Ninja SSE access without assuming advertised Pro access is live.
6. Evaluate self-hosted X1 read-only node vs X1Scroll for history/streaming redundancy.
7. Perform read-only Warp Bridge source discovery and contract verification.
8. Verify Oracle V2's repository-declared X1 program/state through X1 RPC and prove exact layout/freshness semantics under #272 before any provider promotion.
9. Investigate X1 Prism only as an independent bridge-flow cross-check until provenance is proven.

Research boundary: this file summarizes publicly accessible information observed for planning on 2026-08-16. It does not certify current provider uptime, live endpoint access, response semantics, data accuracy, or contractual stability. Those must be established through deterministic provider tests before CMIS relies on them.
