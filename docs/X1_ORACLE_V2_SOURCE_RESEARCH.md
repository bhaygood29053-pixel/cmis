# X1 Oracle V2 Source Research

Research date: **2026-08-26**

Status: **CANDIDATE / RESEARCH ONLY — not an accepted CMIS provider capability**

Tracking issue: **#272** (under X1 provider-gap track #30)

## Purpose

This note records public repository evidence for `jacklevin74/oracle-v2` and defines the CMIS boundary for any future use of that system as read-only X1 price evidence.

Public repository evidence does not establish current X1 deployment health, current account contents, current relay freshness, current signing-key identity, or current price correctness. Those require deterministic live verification before CMIS may rely on the source.

## Source snapshot

Repository:

`https://github.com/jacklevin74/oracle-v2`

Observed default branch: `master`

Pinned research commit:

`97177f772689e44ca4eed9bb95be32ffdf0c5e66`

Commit timestamp recorded by GitHub: **2026-03-26T02:08:36Z**

The reviewed repository commit is unsigned according to GitHub's commit-verification field. This does not by itself invalidate the code, but it must not be treated as cryptographic provenance for the deployed X1 program.

## Repository-supported architecture

The repository describes and implements this flow:

```text
Pyth + CEX price sources
        ↓
multi-source price-feed server
        ↓
five relay clients
        ↓
OpenBao Transit Ed25519 signatures
        ↓
X1 transaction with Ed25519SigVerify + oracle instruction
        ↓
Oracle Vault program / state PDA
```

The price-feed code reviewed at the pinned commit collects Pyth data and CEX prices from Coinbase, Kraken, MEXC, and KuCoin. The code also contains Binance/Bybit pair configuration, but the reviewed main loop passes only MEXC, Coinbase, Kraken, and KuCoin results into aggregation.

The feed computes a weighted median. Pyth observations receive weight `2.0`; the reviewed CEX observations receive weight `1.0` each.

## Repository-declared X1 deployment

The repository declares:

- program ID: `9mPmjK8NxJadYDiHiYAQH4WFCnKJr7ZV8ria63ZkMtv2`
- state PDA: `8XZBqbKhFXHqNGzxV3Tt6gEs9r8ZrNghsRg7zBwLMGJf`
- price decimals: `6`
- relay slots: `5`
- on-chain assets: BTC, ETH, SOL, HYPE, ZEC, FARTCOIN

These values are **repository-declared deployment metadata only** at this stage. CMIS has not yet independently verified the current X1 program account, state-account owner, PDA derivation, account data, program bytecode/deployment identity, or freshness of the stored relay slots.

## Price-feed asset scope

The reviewed price-feed includes source mappings for:

- BTC
- ETH
- SOL
- HYPE
- ZEC
- FARTCOIN
- TSLA
- NVDA
- MSTR
- GOLD
- SILVER

The on-chain Oracle Vault program reviewed at the pinned commit stores six assets only:

- BTC
- ETH
- SOL
- HYPE
- ZEC
- FARTCOIN

Do not infer that every feed-server asset is available on-chain.

## Relay and signing semantics

The relay client:

- fetches the common price-feed server;
- converts six prices to fixed 6-decimal integer values;
- builds a batch message containing relay index, prices, and timestamp;
- obtains an Ed25519 signature from OpenBao Transit;
- places an Ed25519 verification instruction and Oracle Vault instruction in the same transaction;
- submits the transaction through X1 RPC.

The on-chain program checks the Ed25519 pre-instruction bookkeeping against the configured oracle public key/message/signature and relies on the Solana-compatible runtime to perform the cryptographic verification.

### Independence warning

The five relay clients are **not automatically five independent market-price sources**.

In the reviewed architecture, each relay consumes the same aggregated price-feed server. Therefore:

- relay redundancy may support submission/freshness resilience;
- agreement among relay slots may support same-system consistency;
- relay count alone does not prove independent market-source agreement;
- underlying Pyth/CEX source independence must be evaluated separately and fact-specifically.

This distinction is mandatory for CMIS Evidence Receipt / Proof Score semantics.

## Proposed CMIS boundary

If the source passes verification, the preferred integration is read-only:

```text
Roberta
  -> X1 Scout
    -> CMIS
      -> X1 Provider
        -> X1 RPC
          -> Oracle V2 program/state PDA
```

CMIS should not need to:

- run OpenBao;
- possess the Oracle V2 Transit key;
- possess relay wallet keys;
- submit oracle updates;
- build/sign/broadcast Oracle V2 transactions;
- reproduce the upstream price-feed service merely to read accepted on-chain evidence.

A first provider should consume only X1 on-chain state through the existing X1 RPC boundary.

## Candidate read contract

A future bounded provider result should preserve at least:

- source identifier, e.g. `x1_oracle_v2`;
- exact chain;
- program ID;
- state PDA;
- program-account verification state;
- state-account owner verification state;
- account-layout version/evidence;
- asset identity;
- decimals;
- per-relay slot index;
- raw integer price;
- normalized price;
- relay-supplied timestamp and verified timestamp unit;
- CMIS observation slot/time;
- freshness classification;
- eligible/fresh slot count;
- deterministic median when sufficient eligible slots exist;
- warnings/errors;
- provenance/evidence metadata.

No field should be promoted when its identity, unit, scope, freshness, or decoding semantics are ambiguous.

## Required live verification

Before implementation promotion:

1. verify the program account exists on X1 and is executable;
2. verify exact program ID provenance;
3. derive or independently verify the expected PDA from the program contract;
4. verify the state account exists and is owned by the expected program;
5. verify the deployed account layout matches the reviewed contract;
6. inspect relay-slot prices/timestamps without interpreting stale/zero slots as valid;
7. verify timestamp units and establish an explicit CMIS freshness policy;
8. verify observed asset ordering/decimals;
9. establish deterministic malformed/stale/partial behavior;
10. cross-check selected same-fact prices against existing CMIS X1 evidence with exact identity/unit/time gates.

## Promotion constraints

Oracle V2 remains candidate evidence until the normal CMIS gates pass.

In particular:

- repository claims are not live facts;
- a repository-declared deployment address is not accepted on-chain identity until RPC-verified;
- five relay slots do not equal five independent sources;
- same-fact agreement does not prove source independence;
- an upstream weighted median should not be silently represented as a raw exchange price;
- stale or missing slots remain stale/missing;
- CMIS must not add signing, transaction submission, custody, or execution authority as part of this integration.

## Current conclusion

Oracle V2 is a strong candidate for **structurally distinct X1 price evidence** because its on-chain state is fed from an external multi-source oracle pipeline rather than the XDEX market path used by CMIS.

That potential value is not yet accepted capability. The next correct step is deterministic X1 RPC verification of the declared program/state contract under issue #272.
