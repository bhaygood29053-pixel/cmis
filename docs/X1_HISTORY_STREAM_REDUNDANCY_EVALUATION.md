# X1 history and streaming redundancy evaluation

Research baseline: **2026-08-17**  
Reconciled implementation state: **2026-08-27**

## Current decision

CMIS has selected the operator-controlled **official X1 read-only node** as the
next bounded history/streaming redundancy implementation path under #301.

X1Scroll is no longer an active integration candidate. PR #229 was closed after
credential-backed verification could not run because the required API key was
unavailable, and #299 removed X1Scroll from CMIS integration scope.

This document therefore no longer models X1Scroll as the second leg of an
active redundancy architecture.

## Official X1 read-only node

Classification: **OFFICIAL DOCUMENTATION / operator-controlled provider path /
live deployment verification still required**.

Official X1 documentation shows a Tachyon validator read-only configuration with:

- `--full-rpc-api`;
- `--enable-rpc-transaction-history`;
- `--enable-extended-tx-metadata-storage`;
- `--rpc-pubsub-enable-block-subscription`.

The published sample also uses `--limit-ledger-size 50000000`.

Consequences:

- full RPC/history/extended metadata and block PubSub are documented capability
  paths;
- retention remains operator/configuration/storage dependent;
- the sample must not be relabeled as guaranteed unpruned archive history;
- live CMIS use requires empirical identity, history, finality, reconnect, and
  gap/backfill evidence.

Primary sources:

- https://docs.x1.xyz/validating/create-a-read-only-node
- https://docs.x1.xyz/validating/connect-validator-to-x1-mainnet

## #301 implementation

The accepted implementation target is:

```text
X1 Provider
├── official/public X1 RPC                     existing canonical chain RPC
└── operator-controlled X1 read-only node      bounded infrastructure redundancy
```

The separate node may improve:

- operator control;
- availability/failover options;
- controlled historical retention;
- transaction/block verification;
- finalized block PubSub;
- reproducible reconnect/backfill measurements.

It does **not** automatically improve market-source independence.

```text
separate node deployment != independent market observation
RPC agreement != market-source independence
same chain state != independent price formation
```

## Implemented deterministic contract

`liquidity_scout/providers/x1/self_hosted_readonly_node.py` now defines:

1. startup-configuration artifact verification for the four documented required
   capability flags;
2. exact X1 network binding through self-hosted vs canonical `getGenesisHash`;
3. version-response preservation through `getVersion`;
4. health and finalized-slot checks;
5. bounded finalized `getSignaturesForAddress` history sampling;
6. same-signature `getTransaction` comparison against canonical X1 RPC;
7. same-slot `getBlockTime` comparison;
8. infrastructure `AGREEMENT` / `CONFLICT` /
   `INSUFFICIENT_EVIDENCE` classification;
9. block PubSub acknowledgement/slot/duplicate/order classification;
10. reconnect discontinuity evaluation with bounded canonical `getBlocks`
    backfill so skipped slots are not mislabeled as dropped events.

## Live probes

RPC:

`cmis_x1_self_hosted_node_probe.py`

PubSub:

`cmis_x1_self_hosted_block_pubsub_probe.py`

Dedicated workflow:

`.github/workflows/x1-self-hosted-readonly-node-evidence.yml`

The workflow is opt-in. It requires explicit self-hosted endpoint
configuration. Endpoint URLs are never emitted in evidence artifacts.

## Current verification boundary

Deterministic contract implementation does not equal live node verification.

Until an actual self-hosted deployment endpoint/config artifact is supplied and
the probes pass:

```text
network_identity_verified = unavailable
rpc_contract_verified = unavailable
history_sample_verified = unavailable
streaming_verified = unavailable
retention_verified = false
archival_completeness_verified = false
market_source_independence_verified = false
cmis_provider_promoted = false
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

Missing endpoint configuration is a blocked evidence state, not evidence that a
self-hosted X1 node is unavailable or defective.

## Remaining empirical work

After a real node is reachable:

1. run bounded RPC identity/history comparison;
2. capture sanitized startup-config provenance;
3. run two-session finalized block PubSub reconnect/backfill evidence;
4. repeat historical boundary measurements over time before claiming retention;
5. test restart/recovery behavior;
6. measure bounded request/stream capacity only with an explicit methodology;
7. perform three-axis review before any CMIS reliance decision.

## Promotion boundary

A successful bounded RPC or PubSub probe can prove only its exact observed
contract. It must not silently widen into:

- full archive completeness;
- continuous retention;
- complete historical coverage;
- independent price formation;
- independent market-source agreement;
- public-service/Scout promotion;
- execution authority.

No signing, transaction construction, broadcast, custody, staking/voting
operation, trading, bridge transfer, or autonomous value movement is part of
#301.
