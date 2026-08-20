# Wallet Relationship Evidence Boundary

## Status

This document defines the first internal CMIS wallet-relationship evidence contract tracked by Issue #255.

The contract is deliberately **deterministic, evidence-bound, read-only, and non-promoted**. It records only observed direct transfer relationships that can be rebuilt from accepted CMIS wallet-activity observations. It does not infer ownership, beneficial ownership, behavior, intent, risk, or complete graph/history coverage.

## First accepted relationship

```text
schema = cmis_wallet_relationship_evidence.v1
relationship_kind = observed_direct_interaction
interaction_type = verified_token_transfer
```

The accepted source facts are limited to canonical CMIS wallet-activity observations whose activity type is exactly `TRANSFER_IN` or `TRANSFER_OUT` and whose transfer direction and counterparty identity are already verified.

Direction is reconstructed deterministically:

```text
TRANSFER_OUT: wallet -> counterparty
TRANSFER_IN:  counterparty -> wallet
```

CMIS does not accept a caller-supplied relationship label.

## Evidence trust boundary

The relationship builder accepts only a canonical content-addressed wallet-activity observation id:

```text
wa_<64 lowercase hex>
  -> trusted internal observation resolver
  -> complete wallet-activity revalidation
  -> exact observation-id match
  -> direct relationship evidence
  -> wr_<64 lowercase hex>
```

The resolved wallet-activity observation is revalidated through the accepted Phase 11 wallet-activity boundary before relationship construction. A caller/provider assertion is not a trust root merely because it names two wallets or a transaction.

Trusted resolver failures preserve only the exception type. Arbitrary resolver text is neither reflected nor retained in the raised exception chain because storage/provider errors may contain credential-bearing paths, URLs, or provider responses.

The relationship preserves:

- exact chain;
- exact asset identity;
- deterministic sender and recipient;
- transaction/signature identity;
- observation time;
- slot/block when available;
- verified amount and unit when available;
- source;
- verification method;
- evidence scope;
- exact source `wa_...` observation identity;
- explicit verification flags and limitations.

Missing amount remains `null`; it is never converted into zero.

## Evidence Receipt / Proof Score boundary

The accepted `cmis_wallet_activity_observation` primitive does not currently embed an Evidence Receipt or Proof Score record. This contract therefore does **not** manufacture, accept, or substitute caller-supplied receipt/proof objects.

The relationship evidence explicitly records:

```text
evidence_receipt_binding_available = false
evidence_receipt_ids = []
proof_score_binding_available = false
proof_score_records = []
proof_strength_separate_from_risk = true
```

A later evidence-binding or promotion milestone may attach accepted CMIS-owned receipt/proof records only under a separately tested deterministic contract.

## Explicit non-ownership semantics

Every direct relationship and bounded summary preserves these hard invariants:

```text
ownership_inference_added = false
beneficial_ownership_inference_added = false
behavioral_interpretation_added = false
intent_interpretation_added = false
risk_interpretation = null
proof_strength_separate_from_risk = true
complete_history_claimed = false
complete_graph_coverage_claimed = false
provider_assertion_promoted = false
public_service_promoted = false
scout_reliance_promoted = false
cmis_promotable = false
execution_authorized = false
```

An observed transfer between two identities does **not** prove:

- common ownership;
- beneficial ownership;
- control by one person/entity;
- insider or whale status;
- bot or coordinated behavior;
- market-maker status;
- accumulator/distributor behavior;
- intent;
- manipulation;
- fraud/scam activity;
- risk severity;
- complete wallet history;
- complete relationship-graph coverage.

## Bounded compatible summaries

`cmis_wallet_relationship_summary.v1` may summarize only a compatible evidence set with the same:

- chain;
- asset;
- sender;
- recipient;
- source;
- verification method;
- evidence scope.

It may expose only deterministic bounded facts such as:

- first observed interaction time;
- last observed interaction time;
- verified direct-interaction count;
- transaction/signature identities;
- relationship evidence ids;
- source wallet-activity observation ids;
- amount-present versus amount-missing observation counts.

Different chain, asset, direction, source, verification method, or evidence scope fails closed instead of being merged into one relationship summary. Incompatible verified units also fail closed.

## Duplicate evidence rule

The first slice has no separately verified transfer-index contract. CMIS therefore cannot prove that multiple same-pair, same-asset observations inside one transaction are distinct transfer events.

For counting, the contract uses a conservative transaction-scoped interaction key:

```text
chain + asset + sender + recipient + transaction_signature
```

Repeated evidence for the same interaction cannot inflate the interaction count. If duplicate relationship evidence for the same interaction disagrees on observation time, slot/block, amount, or unit, aggregation fails closed rather than selecting one value.

This may conservatively undercount a transaction that contains multiple same-pair/same-asset transfers. The contract explicitly does not claim transfer-event completeness.

## Fail-closed behavior

Relationship construction or aggregation rejects:

- malformed/non-canonical `wa_...` evidence ids;
- missing trusted resolver;
- missing or tampered source observations;
- source observation id mismatch;
- non-transfer wallet activities;
- unverified transfer direction;
- missing/unverified counterparty identity;
- incompatible chain/asset/direction/source/method/scope;
- incompatible verified units;
- conflicting duplicate material facts;
- tampered `wr_...` or `wrs_...` canonical records;
- caller attempts to replace the observed relationship with ownership, behavior, intent, risk, fraud, manipulation, or similar labels.

## Promotion boundary

This module is an internal deterministic foundation only.

It does not:

- add a public CMIS relationship service;
- change `GET /v1/cmis/capabilities`;
- grant Chain Scout reliance;
- change Roberta behavior;
- authorize ownership or behavioral classification;
- authorize automated alerts;
- authorize transaction preparation, signing, broadcasting, custody, trading, bridge transfer, autonomous execution, or value movement.

A later public-service or Scout-reliance promotion requires a separate accepted contract after this evidence foundation and its deterministic tests are accepted.

## Architecture

```text
User / transport
  -> Roberta
    -> Chain Scout
      -> CMIS
        -> Chain Provider / verified source
```

CMIS owns deterministic relationship evidence. Chain Scouts and Roberta may explain accepted results but may not manufacture relationship, ownership, behavior, intent, or risk facts beyond separately accepted contracts.
