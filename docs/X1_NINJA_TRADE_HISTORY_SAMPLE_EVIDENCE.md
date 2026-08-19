# X1.Ninja Trade-History Sample Evidence

## Status

This evidence layer is **bounded and non-promotional**.

It cross-checks a prefix of one already-observed X1.Ninja `/v1/trades/{address}` response against independently produced X1 RPC transaction verification reports. It does not alter the X1.Ninja transport and does not add or guess provider query parameters.

## What a positive sample can establish

For the sampled returned rows only, CMIS can record whether:

- every sampled `txHash` has an exact X1 RPC `VerificationReport`;
- each bound transaction was found and successful at the RPC observation;
- every sampled row's `poolAddress` equals an independently verified requested pool;
- the Ninja `maker` string equals the RPC primary signer as an observational cross-check;
- the Ninja `slot` value exactly equals the independently observed RPC transaction slot;
- the Ninja `type` agrees with wallet-level `SIGNER_OR_ROUTED_BALANCE_DIRECTION` evidence when the transaction verifier reaches `PROVIDER_SIDE_ONCHAIN_CONFIRMED`;
- the returned sampled sequence is or is not monotonic newest-to-oldest by independently verified RPC slot.

The ordering result is an **observation about that returned sample**, not an X1.Ninja ordering contract.

## What remains unverified

This layer does not establish:

- pagination or cursor behavior;
- range parameters or requested time/slot windows;
- exhaustive or complete pool history;
- provider retention depth;
- transaction finality semantics;
- provider timestamp semantics;
- provider amount, price, or USD units/derivation;
- stable provider ordering behavior across requests;
- wallet history completeness;
- CMIS promotion of X1.Ninja history.

An empty returned sample produces no positive completeness flags. A locally truncated sample is explicitly labeled as such.

## Safety

Read-only deterministic evidence composition only. No new network transport, wallet connection, transaction preparation, signing, broadcasting, custody, trading, bridge transfer, autonomous execution, or value movement.

Tracks issue #30.
