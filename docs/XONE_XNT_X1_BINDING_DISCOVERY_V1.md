# XONE/XNT X1 Binding Discovery v1

Status: **IMPLEMENTATION FOR ISSUE #595 — NOT ACCEPTED UNTIL DETERMINISTIC + LIVE BOUNDED-CORPUS GATES PASS AND PR MERGES**

Contract:

`xone_xnt_x1_binding_discovery/v1`

## Purpose

This contract searches for the first exact **X1-side account/program binding** in the dedicated XONE→XNT evidence track.

The target is narrow: an exact 32-byte X1/SVM public key must appear in a bounded source statement that explicitly contains **both XONE and XNT** and uses conversion/migration/burn/redeem/claim/allocation/vesting/unlock/distribution/issuance language.

This is deliberately stricter than ordinary XNT reward discovery.

## Binding rule

A candidate may be discovered only when all of the following are true:

1. the source claim is inside the bounded dedicated XONE/XNT corpus;
2. the excerpt explicitly contains `XONE`;
3. the excerpt explicitly contains `XNT`;
4. the excerpt contains binding/mechanism language;
5. the candidate string decodes to exactly 32 bytes under the SVM Base58 alphabet.

XNT-only validator reward, staking, lockup, or unlock rules are **not** XONE→XNT binding evidence.

## Built-in infrastructure boundary

Known SVM infrastructure programs such as the System Program, Stake Program, Vote Program, Compute Budget Program, and BPF Upgradeable Loader may be recognized if they appear in source text, but they are not treated as custom XONE→XNT binding candidates and are not history-scanned by this contract.

## Direct X1 history qualification

For a custom exact candidate, v1 may perform read-only finalized X1 RPC:

- `getAccountInfo(..., jsonParsed, finalized)`;
- bounded `getSignaturesForAddress(..., finalized)`;
- bounded successful `getTransaction(..., jsonParsed, finalized)`.

The transaction parser preserves only structural activity facts needed for future review:

- exact candidate reference in account keys;
- exact invoked program ids;
- parsed System Program native transfers involving the candidate;
- candidate native-lamport balance delta when directly available.

A native transfer, positive balance delta, executable account, or repeated transaction history does **not** prove distribution, allocation, vesting, claim, or conversion role.

## Live corpus

The acceptance workflow inspects a bounded corpus containing:

- X1 official website;
- X1 Docs root;
- the accepted official incentivized-testnet-rewards page;
- X1 developer surface;
- bounded ranked X1 Report XONE/XNT sitemap pages as secondary discovery.

At least two official X1 pages, including the rewards page, and at least one X1 Report ranked page must be available for the live source gate.

## Valid zero-candidate result

A live PASS may legitimately return:

```text
candidate_count = 0
x1_binding_identified = false
```

This means only that the **bounded inspected corpus** did not expose an exact X1/SVM account or program inside an explicit XONE/XNT binding statement.

It does not prove no XONE→XNT mechanism exists.

## Authority boundary

Even a technically qualified custom account keeps:

```text
source_binding_verified = false
candidate_role_verified = false
x1_binding_identified = false
xnt_distribution_mechanism_identified = false
xnt_issuance_verified = false
xnt_vesting_or_unlock_verified = false
xone_xnt_conversion_verified = false
cross_chain_correlation_verified = false
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

A later contract must bind an exact candidate to authoritative XONE→XNT semantics before any of those fields can change.

## Next slice after acceptance

If this bounded corpus yields no exact X1 binding, broaden only to additional authoritative/public XONE sources that can be provenance-qualified, plus exact X1 chain-history pivots derived from a verified candidate. Do not scan arbitrary X1 addresses or promote wallet activity by pattern matching alone.
