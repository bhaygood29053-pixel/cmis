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
