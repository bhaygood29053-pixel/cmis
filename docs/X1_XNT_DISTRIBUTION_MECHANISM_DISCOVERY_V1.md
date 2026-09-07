# X1 XNT Distribution / Vesting Mechanism Discovery v1

Status: **ACCEPTED INTERNAL CONTRACT** via Issue #592 / PR #593. X1 XNT Distribution Mechanism Discovery run #1 passed deterministic and live official-source jobs at head `34b3e7ac9d9d9370b38575c3a47883e351c2c5e9`, Liquidity Scout Tests run #1770 passed, and PR #593 merged as `afb752f2f1ea4084836921abc8505243b858abb5`.

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

## Accepted live result

The official X1 incentivized-testnet-rewards page was available as `text/markdown` and the accepted parser produced **17 bounded XNT mechanism claims**.

The live source contained the currently documented validator-reward mechanics, including:

- `50,000 Credits = 1 XNT` / `50,000 credits = 1 XNT`;
- `10%`;
- `90%`;
- `365 Days` / `365 days`;
- validator reward, allocation, distribution, lockup, vesting, claim, genesis, stake, and unlock contexts.

The bounded official page contained **0 exact 32-byte X1/SVM pubkey candidates**, so no X1 account/program was qualified in this run. The evidence artifact digest is `sha256:bba687ec9235fee723c8fc945fe46f5f02e71a816418371f30630699c4c9957d`.

That is a valid scoped result:

`zero_candidates_mean_only_no_exact_pubkeys_in_supplied_claims=true`

It means only that this official page did not name an exact account/program candidate. It is **not** evidence that no XNT distribution/vesting/claim account or program exists.

## Authority boundary

```text
xnt_rule_claim_verified = false
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

The contract is read-only. It does not create, sign, claim, vest, unlock, stake, transfer or burn anything.

## Next slice

Use the accepted official-rule result to separate known validator-reward mechanics from the still-unproven XONE→XNT mechanism. The next gate should search primary X1/XONE sources and bounded X1 history for an **exact account/program binding** that explicitly connects an Ethereum XONE conversion/burn event to XNT allocation, claim, vesting or distribution.
