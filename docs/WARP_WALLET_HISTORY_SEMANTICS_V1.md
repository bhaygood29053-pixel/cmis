# Warp Wallet History Semantics v1

Issue context: #409 / completed #433

## Purpose

The connected official Warp History response is useful corroborating evidence,
but it is **not** the canonical settled-event source for Bridge Flow
Intelligence.

Canonical settled-event authority is:

`warp_onchain_transfer_history/v1`

accepted through PR #436.

This document records the exact wallet API body without creating a second truth
path.

## Exact response identity

Exact canonical response SHA-256:

`e309a68509b631002c46526e772ac0b40d2381a21ff2bef46c7c56cbaa4dcca5`

Repository fixtures redact the wallet, sender, and recipient identifiers.

Sanitized fixture canonical SHA-256:

`e4e94c4086cf92736d018367ac4edaee809b96cbda5387d600917ff4008e2195`

## Observed response

Top-level fields:

- `wallet`;
- `transactions`;
- `count = 2`;
- `source = sqlite`.

Observed transaction statuses:

- `executed`;
- `signing`.

The executed row also exposes:

- source `txSig`;
- `sourceSlot` and `slot`;
- `signaturesCollected = 7`;
- `signaturesRequired = 5`;
- `destTxSig` and `submissionTxSig`;
- `destSlot` and `submissionSlot`.

The signing row has only one collected signature, zero source slot, and no
destination execution references.

Those observations are useful status/reference corroboration. They do not
replace the accepted on-chain OutgoingMsg/IncomingMsg pairing proof.

## Exact route context

The first fixture is Solana -> X1 USDC.

Accepted route context:

- Solana USDC mint: `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`;
- X1 USDC.X mint: `B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq`;
- decimals context: 6.

The API row itself contains only the provider token label `USDC`, not exact
mints. Therefore:

`row_exact_mint_identity_verified=false`

The exact route identity still comes from the accepted config/provenance/on-chain
evidence path.

## Amount and timestamp limits

The row contains integer `amount` values, but this wallet-response contract
does not independently prove their unit semantics:

`provider_amount_unit_semantics_verified=false`

The row `timestamp` is accepted as Unix milliseconds attached to the provider
transaction record. It is **not** promoted as destination settlement time:

`provider_timestamp_is_settlement_time=false`

Canonical settlement time remains the on-chain IncomingMsg
`executed_timestamp` under `warp_onchain_transfer_history/v1`.

## Coverage

The endpoint is wallet-scoped:

`GET /api/bridge/transactions/wallet/{wallet}?limit=100`

Therefore it cannot prove route-wide bridge coverage.

```text
route_wide_coverage_verified = false
pagination_coverage_verified = false
flow_event_normalization_authorized = false
```

This is consistent with the stronger route-wide discovery evidence already
accepted in PR #436: real paired settled events exist, but historical retention
coverage is still unverified, so #409 primary 24h/7d/30d totals remain null.

## Privacy and authority

Wallet/sender/recipient identifiers are redacted from repository fixtures and
semantic outputs.

```text
corroboration_only = true
read_only = true
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```
