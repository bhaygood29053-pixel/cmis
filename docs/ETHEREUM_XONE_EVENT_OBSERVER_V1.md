# Ethereum XONE Event Observer v1

Status: **IMPLEMENTATION FOR ISSUE #583 — NOT ACCEPTED UNTIL DETERMINISTIC + LIVE MULTI-RPC GATES PASS AND PR MERGES**

Contract:

`ethereum_xone_event_observer/v1`

## Accepted dependency

The observer is anchored to the exact Ethereum XONE identity accepted under `ethereum_xone_identity/v1`:

- contract: `0x4DCDa2274899d9BbA3Bb6f5A852C107Dd6E4fE1c`
- Ethereum mainnet chain ID: `0x1`
- decimals: `18`

The observer never selects a token by symbol or name.

## Event scope

The observer queries only canonical ERC-20:

`Transfer(address,address,uint256)`

topic:

`0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef`

and only when emitted by the exact accepted XONE contract.

Each accepted event preserves:

- transaction hash;
- block hash;
- block number;
- block timestamp;
- log index;
- source address;
- destination address;
- exact integer base-unit amount;
- exact decimal XONE rendering at 18 decimals;
- deterministic event ID.

Removed/reorged rows, wrong emitters, non-Transfer topic0 values, malformed indexed addresses, malformed uint256 data, out-of-window rows and ambiguous zero→zero events fail closed.

## Classification

The direct event classifier is deliberately narrow:

| condition | direct classification | what is verified |
| --- | --- | --- |
| `to == 0x000...000` | `burn` | exact XONE Transfer-to-zero burn event |
| `from == 0x000...000` | `mint` | exact XONE Transfer-from-zero mint event |
| both nonzero | `transfer` | exact XONE token movement |

A current-code lookup may optionally flag a nonzero recipient as a contract-recipient candidate. That flag is discovery assistance only.

A transfer to a contract does **not** prove:

- lock;
- migration;
- bridge deposit;
- conversion deposit;
- snapshot/eligibility;
- claim;
- XNT issuance.

Therefore every event and every observation keeps:

```text
lock_or_migration_verified = false
xone_xnt_conversion_verified = false
xnt_issuance_verified = false
cross_chain_correlation_verified = false
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

## Bounded-window rule

One observation covers an explicit inclusive block range. Default implementation limits are:

- maximum 5,000 blocks per request;
- maximum 2,000 Transfer events per returned window.

Larger histories must be paginated. A zero-event result means only that no matching canonical XONE Transfer logs were returned inside that exact verified window. It never means zero lifetime XONE activity.

## Multi-RPC corroboration

Live acceptance requires at least two distinct public Ethereum RPC transport hosts to agree on:

- exact block window;
- event identities;
- event classifications;
- transaction/block/log identity;
- from/to addresses;
- exact base-unit amounts;
- block timestamps.

Provider transport diversity is not treated as independent semantic/source authority: all providers are observing Ethereum consensus.

## XONE/XNT handoff

The dedicated conversion-intelligence service performs the live exact-XONE identity check before observing an event window.

The handoff may elevate:

- `ethereum_xone_identity_verified=true`;
- `ethereum_event_window_verified=true`;
- `ethereum_event_verified=true` only when one or more canonical events exist;
- `xone_burn_verified=true` only when at least one exact Transfer-to-zero event exists.

It may not elevate any X1-side or cross-chain conclusion.

## Next slice after acceptance

After this observer is accepted, the next XONE/XNT slice is to identify and verify any exact Ethereum recipient contract/address that is actually documented or on-chain-proven to be a XONE lock/migration/conversion sink. Only then may CMIS distinguish an ordinary contract transfer from an actual migration deposit.
