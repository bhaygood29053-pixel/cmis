# Self-hosted X1 read-only node evidence contract

Status: **implementation / live deployment evidence still required**

Tracking: **#301**

## Purpose

CMIS may use an operator-controlled official X1 read-only node as bounded
infrastructure redundancy for historical RPC and block PubSub evidence beneath
the X1 Provider.

```text
Roberta -> X1 Scout -> CMIS -> X1 Provider -> self-hosted X1 read-only node
```

This contract does not turn a separately operated node into an independent
market-price source.

## Official configuration basis

The official X1 read-only-node guide currently documents a Tachyon validator
configuration containing:

```text
--full-rpc-api
--enable-rpc-transaction-history
--enable-extended-tx-metadata-storage
--rpc-pubsub-enable-block-subscription
```

The sample also uses `--limit-ledger-size 50000000`, so the published example
must not be interpreted as an unpruned archive guarantee.

Sources:

- https://docs.x1.xyz/validating/create-a-read-only-node
- https://docs.x1.xyz/validating/connect-validator-to-x1-mainnet

The Solana-compatible `blockSubscribe` contract is explicitly unstable and is
available only when block subscription is enabled; the X1 node contract
therefore verifies its observed message/reconnect behavior instead of assuming
the format from documentation alone.

## Implementation

### Deterministic core

`liquidity_scout/providers/x1/self_hosted_readonly_node.py` owns:

- startup-configuration artifact evaluation;
- genesis-hash network identity comparison;
- node version-shape preservation;
- finalized bounded historical same-fact comparison;
- block PubSub transcript classification;
- reconnect/discontinuity/backfill evaluation;
- explicit non-promotion and non-independence semantics.

### RPC probe

`cmis_x1_self_hosted_node_probe.py` performs a bounded comparison between an
explicit self-hosted endpoint and the accepted canonical X1 RPC endpoint.

Methods:

- `getGenesisHash`;
- `getVersion`;
- `getHealth`;
- `getSlot` with finalized commitment;
- `getSignaturesForAddress` with finalized commitment;
- `getTransaction` for one finalized successful sample;
- `getBlockTime` for the same sample slot.

The output intentionally omits endpoint URLs and raw transactions.

A passing bounded sample may establish:

```text
network_identity_verified = true
rpc_contract_verified = true
history_sample_verified = true
```

It does not establish:

```text
retention_verified = false
archival_completeness_verified = false
continuous_coverage_verified = false
market_source_independence_verified = false
cmis_provider_promoted = false
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

### Startup configuration evidence

`evaluate_startup_configuration` requires both:

1. an operator-supplied startup command/config artifact; and
2. non-empty provenance.

It checks the exact required capability flags as tokens. Even when the supplied
artifact passes, `running_process_configuration_verified=false` remains
authoritative because a text artifact does not remotely attest the current
process command line.

### Block PubSub probe

`cmis_x1_self_hosted_block_pubsub_probe.py` opens two finalized
`blockSubscribe` sessions separated by a deliberate reconnect.

Each session records only sanitized structural evidence:

- acknowledgement/subscription ID;
- observed context slots;
- duplicate slots;
- out-of-order state;
- malformed-message count.

Across the reconnect, slot discontinuities are **not** automatically labeled
as dropped events. Recent canonical X1 `getBlocks` backfill is used to
distinguish produced intermediate blocks from skipped slots. Unknown/unbounded
backfill remains insufficient evidence.

The probe never stores raw block payloads or endpoint URLs.

## Agreement semantics

A same-signature/same-slot/same-block-time match between the self-hosted node
and canonical X1 RPC may be classified as **infrastructure agreement**.

It does not prove market-source independence:

```text
separate node deployment != independent market observation
RPC agreement != market-source independence
same chain state != independent price formation
```

This distinction is mandatory in CMIS evidence.

## Failure behavior

Fail closed on:

- missing explicit self-hosted/canonical endpoint configuration;
- genesis mismatch;
- malformed/non-object version response;
- non-`ok` health;
- malformed finalized slot/history/transaction/block-time evidence;
- non-finalized history sample;
- transaction signature or slot mismatch;
- block-time disagreement;
- malformed PubSub acknowledgement/notification;
- out-of-order stream transcript;
- incomplete canonical reconnect backfill.

Conflicts are preserved. CMIS does not average, prefer, or silently reconcile
incompatible chain-state evidence.

## Local RPC probe

```bash
python cmis_x1_self_hosted_node_probe.py \
  --rpc-url http://127.0.0.1:8899 \
  --canonical-rpc-url https://rpc.mainnet.x1.xyz \
  --probe-address <FINALIZED_HISTORY_ADDRESS> \
  --output x1-self-hosted-rpc-evidence.json
```

Optional startup artifact:

```bash
  --startup-command-file /path/to/sanitized-validator-command.txt \
  --startup-config-provenance "operator captured from deployment config"
```

Do not put private keys, identity key material, bearer tokens, or other secrets
in the startup artifact.

## Local PubSub probe

The WebSocket URL must be explicit; CMIS does not guess RPC+1 port mappings.

```bash
python cmis_x1_self_hosted_block_pubsub_probe.py \
  --ws-url ws://127.0.0.1:<EXPLICIT_PORT> \
  --canonical-rpc-url https://rpc.mainnet.x1.xyz \
  --notifications-per-session 3 \
  --output x1-self-hosted-pubsub-evidence.json
```

## Live CI boundary

The dedicated workflow is opt-in/manual. Live evidence requires configured
self-hosted endpoint secrets and an explicit probe address. Missing
configuration is a blocked verification state, not provider failure.

Until both bounded RPC evidence and the required deployment/PubSub evidence
are collected and accepted, #301 remains non-promoted and the provider-gap
status remains partial/missing.

## Execution boundary

Read-only verification only. No transaction construction, signing, broadcast,
custody, trading, bridge transfer, validator voting/staking operation, or
autonomous value movement is introduced.
