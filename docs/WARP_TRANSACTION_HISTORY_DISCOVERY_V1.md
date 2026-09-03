# Warp Transaction History Discovery v1

Issue: #433  
Parent: #409

## Purpose

Establish the exact live read-only transaction/history surface required to feed
the already merged `bridge_flow_intelligence/v1` calculator.

This discovery contract does **not** yet promote live Warp transfer totals.

Contract:

`warp_transaction_history_discovery/v1`

## Candidate source

Current candidate base URL:

`https://api.bridge.mainnet.x1.xyz`

Candidate transaction list:

`GET /transactions?status=<status>&limit=<n>&page=<n>`

Candidate per-transaction guardian/message view:

`GET /transactions/:txSig/signatures`

A pinned public Warp dashboard repository independently documents those read-only
interfaces and the same base URL:

- repository: `nibty/warp-bridge-dashboard`
- commit: `6a9ea7187879778d3a46e313d1fec177541adce8`
- spec: `docs/superpowers/specs/2026-07-17-offchain-partial-signatures-design.md`

That third-party repository is corroborating evidence only. CMIS still requires
its own live observation and field-level acceptance.

## Discovery fields

The live workflow records only a sanitized subset of the transaction page:

- `txSig`
- `from`
- `to`
- `status`
- `token`
- `amount`
- `sender`
- `recipient`
- `sourceSlot`
- `timestamp`
- `signaturesCollected`
- `signaturesRequired`

It separately inspects the non-secret message fields attached to guardian
signature records:

- `seq`
- `sourceChainId`
- `destChainId`
- `guardianSetIndex`
- `sender`
- `token`
- `amount`
- `timestamp`

Raw guardian signatures are never retained.

## What must be proved before #409 can consume the source

The source may not feed `bridge_flow_intelligence/v1` until CMIS can
deterministically prove:

1. exact transfer/event identity;
2. exact route mapping to the accepted #407 mint-pair route;
3. exact amount units and decimals;
4. source/destination direction;
5. which lifecycle state is settled/final;
6. settlement timestamp and timestamp unit;
7. duplicate/replay/refund/failure handling;
8. pagination semantics;
9. historical coverage completeness.

A successful HTTP response does not prove any of those semantics by itself.

## Coverage boundary

The list endpoint's `total`, `page`, `pageSize`, or equivalent pagination
metadata may help enumerate records, but page metadata alone never proves
historical completeness or retention.

Until a separate completeness argument is accepted:

`coverage_complete_verified=false`

and missing periods remain unknown, never zero.

## Safety

The discovery workflow uses GET requests only.

It never:

- constructs bridge transfers;
- signs;
- broadcasts;
- invokes admin/rpc/send/confirm endpoints;
- moves value;
- promotes the source to Scout/ROBERTA.

`execution_authorized=false`.


## 2026-09-03 live API observation

The first exact-head discovery run established that the candidate API is live
and returns executed records, but it is not sufficient by itself for accepted
history coverage.

Observed page 1 for `status=executed&limit=50&page=1`:

- HTTP 200 / `application/json`;
- `total=61`;
- `page=1`;
- `pageSize=50`;
- 50 executed transaction records;
- fields included `txSig`, `destTxSig`, `from`, `to`, `token`,
  `amount`, `sourceSlot`, `destSlot`, `timestamp`, sender/recipient and
  signature-count fields.

The corresponding page-2 request returned HTTP 200 but an empty page with
`total=0`. Therefore pagination semantics and complete retention cannot be
accepted from this API response.

The per-transaction `/signatures` response for an executed sample also
contained no guardian messages. Therefore the executed-list API alone does not
supply the sequence number or exact mint identity needed for deterministic
route pairing.

This is a useful negative result. CMIS must not treat the API's `total`,
token symbol, or first page as complete bridge-flow history.

## On-chain transfer-state path

The pinned Warp IDL and already accepted program identity expose a stronger
read-only source directly from chain state:

- `OutgoingMsg` account discriminator with current size 106;
- `IncomingMsg` account discriminator with current size 116;
- legacy `IncomingMsg` size 107;
- `OutgoingMsg` PDA seeds `["evt_out", seq]`;
- `IncomingMsg` PDA seeds `["evt_in", source_seq]`.

The on-chain normalizer requires:

1. exact Warp program owner;
2. exact Anchor account discriminator;
3. exact supported account length;
4. reproducible PDA including the stored bump;
5. exact source sequence pairing;
6. exact sender equality;
7. exact amount equality;
8. exact source timestamp equality;
9. exact source and destination mints from the accepted route;
10. expected lock/burn and mint/release operation topology;
11. destination `processed=true`;
12. a positive destination execution timestamp for immediate transfers.

Only then may it emit a normalized settled event for
`bridge_flow_intelligence/v1`.

### Delayed claims

A processed delayed transfer is not given an invented settlement time.

If `claimable_after > 0`, the event remains unresolved in this slice even when
`claimed=true`, because the current account layout does not itself expose the
actual claim transaction timestamp. A later transaction-history proof may
resolve that timestamp.

## Coverage remains separate

Current program-account enumeration can prove that the paired accounts exist
now. It does not yet prove that every historical message account has been
retained since the beginning of the requested 24h/7d/30d windows.

Therefore even after real paired events are accepted:

`historical_retention_complete_verified=false`

`coverage_complete_verified=false`

The merged flow calculator may ingest those real events, but its primary window
totals remain `null` until the coverage gate is separately satisfied.
