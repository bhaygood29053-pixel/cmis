# Warp Wallet History Semantics v1

Issue: #433  
Parent: #409

## Accepted response fixture

The connected official History API returned one wallet-scoped response with:

- top-level `source = sqlite`;
- `count = 2`;
- one `executed` Solana -> X1 USDC record;
- one `signing` Solana -> X1 USDC record.

Exact response canonical SHA-256:

`e309a68509b631002c46526e772ac0b40d2381a21ff2bef46c7c56cbaa4dcca5`

The wallet/sender/recipient identifiers are not retained in repository fixtures.
The sanitized fixture canonical SHA-256 is:

`e4e94c4086cf92736d018367ac4edaee809b96cbda5387d600917ff4008e2195`

## Exact route binding

The first accepted semantic slice is intentionally narrow:

- direction: Solana -> X1;
- provider token label: `USDC`;
- exact Solana mint: `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`;
- exact X1 mint: `B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq`;
- decimals: 6;
- route identity comes from accepted Warp route qualification, never from the string `USDC` alone.

The observed `amount` field is preserved as integer raw token units under the
accepted exact-mint/decimals route binding. `depositAmount` and `xntAmount`
remain uninterpreted provider fields and are not used for flow truth.

## Lifecycle semantics

Observed statuses in this accepted fixture are only:

- `executed`;
- `signing`.

No broader status enumeration is claimed.

An `executed` row is only a **destination settlement candidate** when:

- source `txSig` exists;
- `sourceSlot == slot > 0`;
- `signaturesCollected >= signaturesRequired`;
- `destTxSig == submissionTxSig`;
- `destSlot == submissionSlot > 0`.

Even then:

```text
settlement_verified = false
pairing_verified = false
settled_at = null
flow_event_eligible = false
```

until the destination transaction and block time are corroborated against the
canonical X1 RPC.

A `signing` row is never eligible for settled flow.

## Timestamp semantics

The response `timestamp` is verified only as Unix milliseconds attached to
the provider transaction row.

Because the record also carries a distinct destination slot, CMIS does **not**
reinterpret `timestamp` as destination settlement time.

For the executed fixture:

`timestamp = 1785414802165`

which is:

`2026-07-30T12:33:22.165Z`

This timestamp is not used as `settled_at`.

## Canonical destination settlement proof

`warp_destination_rpc_settlement/v1` requires the provider-declared
destination transaction signature and destination slot to agree with canonical
X1 RPC:

1. `getTransaction(signature, commitment=finalized)`;
2. returned transaction slot must equal the provider destination slot;
3. first transaction signature must equal the provider destination signature;
4. `meta.err` must be null;
5. `getBlockTime(destination_slot)` must return a positive timestamp;
6. if `getTransaction.blockTime` is present, it must equal `getBlockTime`.

Only after all checks pass may CMIS construct the settled normalized event
required by `bridge_flow_intelligence/v1`.

## Coverage limitation

This endpoint is wallet-scoped:

`/api/bridge/transactions/wallet/{wallet}?limit=100`

Therefore it does **not** prove route-wide Warp transaction coverage.

Even a verified settled event from this response must enter the #409 flow engine
with:

```text
coverage_verified = false
route_wide_coverage_verified = false
pagination_coverage_verified = false
```

until a separate route-wide history/coverage source is accepted.

This prevents one wallet's absence of transfers from becoming a false global
zero.

## Privacy

Repository fixtures redact:

- wallet;
- sender;
- recipient.

CMIS semantic output does not retain those identifiers.

## Authority

```text
read_only = true
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```
