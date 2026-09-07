# X1 XNT Distribution / Vesting Mechanism Discovery v1

Status: **IMPLEMENTATION FOR ISSUE #592 — NOT ACCEPTED UNTIL DETERMINISTIC + LIVE OFFICIAL-SOURCE GATES PASS AND PR MERGES**

Contract:

`x1_xnt_distribution_mechanism_discovery/v1`

## Purpose

This is the first dedicated X1-side evidence contract in the XONE/XNT conversion track.

It answers two different questions without collapsing them:

1. what X1 publicly says about XNT reward distribution, lockup, vesting, claim and unlock rules;
2. whether any exact X1/SVM account or program address named in that bounded source can be qualified directly through X1 RPC.

It does **not** infer that a validator-reward rule is the XONE→XNT conversion rule.

## Native XNT boundary

XNT is treated as X1 native value. WXNT/SPL representations are not substituted for native XNT mechanism evidence.

The contract does not use an SPL mint label as an identity shortcut for XNT distribution.

## Primary acceptance source

The live gate uses the official X1 documentation page:

`https://docs.x1.xyz/validating/validator-rewards/incentivized-testnet-rewards`

The source parser is expected to find the currently documented validator-reward mechanics, including the source's statements about:

- validator/testnet credits and XNT;
- `50,000 credits = 1 XNT`;
- `10%` immediate distribution;
- the remaining `90%`;
- a `365 days` lock/vesting period;
- unlock timing after the lock period.

These are **official-source claims**. They are not transformed into direct-chain truth merely because X1 Docs published them.

If the source changes materially, the live gate fails visibly so the contract can be reconciled to the new official wording.

## Exact X1 candidate extraction

Only strings that decode to exactly 32 bytes under the SVM Base58 alphabet are accepted as X1 account/program candidates.

For each exact candidate, CMIS may call:

`getAccountInfo(candidate, {"encoding":"jsonParsed","commitment":"finalized"})`

and preserve:

- account presence/absence at that exact pubkey;
- finalized context slot when supplied;
- owner;
- executable state;
- lamports;
- space;
- parsed program/type where available.

## Stake lockup structural evidence

If an exact candidate is owned by:

`Stake11111111111111111111111111111111111111`

and the finalized parsed account includes `meta.lockup`, CMIS may preserve:

- lockup epoch;
- lockup Unix timestamp;
- custodian;
- `stake_lockup_state_verified=true`.

That proves only the parsed lockup state of that exact stake account.

It does **not** prove:

- the account is a validator-testnet reward allocation;
- the account belongs to an XONE holder;
- the lockup is the XONE→XNT lockup;
- XNT was issued because XONE was burned;
- any conversion ratio or eligibility rule.

Therefore v1 keeps:

```text
candidate_role_verified = false
xnt_distribution_mechanism_identified = false
xnt_issuance_verified = false
xnt_vesting_or_unlock_verified = false
xone_xnt_conversion_verified = false
cross_chain_correlation_verified = false
```

## Zero-candidate result

A live source can legitimately contain XNT reward/vesting rules but no exact 32-byte X1 pubkey.

That is a valid scoped result:

`zero_candidates_mean_only_no_exact_pubkeys_in_supplied_claims=true`

It is **not** evidence that no XNT distribution/vesting/claim account or program exists.

## Authority boundary

```text
xnt_rule_claim_verified = false
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

The contract is read-only. It does not create, sign, claim, vest, unlock, stake, transfer or burn anything.

## Next slice after acceptance

Use the official-rule result to separate known XNT validator reward mechanics from the still-unproven XONE→XNT mechanism. Then search primary X1/XONE sources and direct X1 history for an exact account/program binding that explicitly connects an Ethereum XONE conversion/burn event to XNT allocation, claim, vesting or distribution.
