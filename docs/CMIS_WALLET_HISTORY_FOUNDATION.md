# CMIS Wallet Activity & Historical Storage Foundation

Status: **read-only intelligence foundation**

This layer follows the evidence-quality work completed in CMIS contract 1.7.x. It does not create wallet labels and does not add a public wallet-intelligence service until provider/chain extraction contracts are separately accepted.

## Wallet activity primitives

`liquidity_scout/cmis/wallet_activity.py` provides deterministic, content-addressed factual observations for:

- transfer in;
- transfer out;
- verified buy;
- verified sell;
- LP addition;
- LP removal;
- deployer-originated transfer;
- balance change.

The summary contract exposes:

- first observed activity;
- last observed activity;
- observed activity window;
- unique transaction count;
- primitive counts;
- compatible verified amounts by asset/unit;
- compatible verified trade volume by quote unit;
- the underlying factual observations.

Every summary states that continuous wallet-history coverage is not proven and that behavioral/identity classification is not authorized.

### Required proof gates

- wallet identity must be verified for every observation;
- asset identity must be verified for asset-scoped observations;
- BUY/SELL requires explicit verified trade direction;
- LP_ADD/LP_REMOVE requires explicit verified LP-action semantics;
- deployer-originated transfer requires independently verified deployer identity;
- counterparties are exposed only when counterparty identity is verified;
- amounts/quote values are exposed only when their verification flags are true.

Missing amounts remain `null`. They are never converted to zero.

## No wallet labels

The wallet primitive contract exposes no classification field other than:

```text
classification_authorized = false
classifications = []
```

CMIS does not call wallets insiders, whales, bots, accumulators, distributors, market makers, manipulators, or similar labels in this foundation.

## Persisted intelligence history

`liquidity_scout/cmis/intelligence_history.py` is a SQLite-backed sanitized observation ledger for these categories:

- wallet;
- price;
- liquidity;
- supply;
- activity.

Each history observation records:

- chain;
- category;
- exact subject identity;
- metric;
- normalized numeric value and unit;
- observation time;
- slot/block when available;
- source;
- verification method;
- evidence scope;
- optional CMIS receipt ID and proof strength;
- identity/semantics/freshness/scope proof state;
- limitations.

Observations are content-addressed and idempotent.

### Historical comparison boundary

The ledger may compare first and last stored observations only when chain, category, subject, metric, unit, and evidence scope are compatible.

It does **not**:

- interpolate missing samples;
- fill gaps with zero;
- claim continuous coverage;
- claim archival completeness;
- convert units;
- reconcile incompatible scope;
- infer missing wallet activity.

A two-sample observed change is exactly that: a sparse observed change, not proof of what happened between the samples.

## Architecture

```text
Provider / chain evidence
        ↓
Deterministic verifier
        ↓
CMIS Evidence Receipt + Proof Score
        ↓
Wallet activity primitive / normalized history observation
        ↓
Sanitized persistent history
        ↓
Future deterministic wallet relationships / Roberta interpretation
```

Roberta may later explain these facts but cannot manufacture classifications that CMIS has not established.

## Execution boundary

This foundation adds no transaction construction, signing, broadcasting, custody, swap execution, bridge transfer, autonomous trading, or value movement.
