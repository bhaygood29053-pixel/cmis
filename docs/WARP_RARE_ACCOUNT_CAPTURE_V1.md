# Warp rare-account capture v1

Issue: #425  
Parent: #407  
Depends on: #419 / PR #423

## Purpose

Advance the accepted zero-byte Warp program-account inventory into a bounded,
read-only byte-evidence capture for the rare account-size families shared by
Solana and X1.

The accepted rare structural families are:

- 170 bytes;
- 236 bytes;
- 321 bytes;
- 335 bytes.

Account size is only a discovery signal. It does not identify configuration,
guardian, route, custody, fee, cap, mint, pause, health, or any other semantic
role.

## Contract

`warp_rare_account_capture/v1`

## Capture boundary

For each chain, CMIS first re-runs the accepted zero-byte
`getProgramAccounts` inventory for the exact Warp program:

`6JbPTuxVuoTgyQeXFb9MH8C8nUY8NBbLP1Lu4B13JfMD`

Only exact Warp-owned accounts whose reported `space` is one of
170/236/321/335 are selected. Selection fails closed above 16 candidates per
chain.

Each candidate is then fetched through read-only `getAccountInfo` with base64
encoding and the requested commitment.

The capture verifies:

- exact Warp program ownership;
- inventory-reported byte length equals decoded account length;
- a valid RPC observation slot exists;
- lamports are present and non-negative;
- the account is non-executable for this v1 state-capture boundary;
- account bytes decode as valid base64.

The request pubkey is preserved as the identity key for the corresponding
`getAccountInfo` response. Solana-compatible `getAccountInfo` returns the
account value and context but does not echo the pubkey inside `result`, so v1
does not invent a server-returned pubkey field.

## Permanent evidence surface

For each account CMIS records:

- chain;
- pubkey;
- structural family / byte length;
- exact owner;
- lamports;
- executable flag;
- RPC observation slot;
- SHA-256 of the complete decoded bytes;
- at most 32 bytes of prefix hex;
- at most 32 bytes of suffix hex.

Full base64 account material is optional and ephemeral. It is not committed as
a permanent source fixture and the live CI gate does not upload it as an
artifact.

## Cross-chain comparison

Only exact pubkey overlaps are compared. For each overlap v1 reports:

- whether reported space matches;
- whether the full-byte SHA-256 matches;
- whether bounded prefix hex matches;
- whether bounded suffix hex matches.

Byte equality does not promote semantic-role equivalence.

## Explicitly not proven

This contract does not prove:

- config-account identity;
- guardian-account identity;
- route identity;
- pause or health semantics;
- fee or cap semantics;
- mint or asset semantics;
- backing or custody model;
- field offsets or field types;
- timestamp semantics;
- Warp qualification.

The required contract flags remain:

```text
account_role_verified=false
binary_layout_verified=false
semantic_contract_accepted=false
cmis_promotable=false
execution_authorized=false
```

## Live evidence

`.github/workflows/warp-rare-account-capture-evidence.yml` runs the deterministic
contract tests and then performs the bounded read-only capture independently on
Solana and X1. The workflow asserts candidate ceilings, exact ownership, byte
lengths, non-executable state, byte hashes, bounded prefix/suffix output, and
the fail-closed promotion flags.

The workflow may hold full base64 material only in runner memory for validation;
it prints only bounded structural evidence and does not upload raw material.

## Relationship to #407

This slice gives #407 independently reproducible byte evidence for rare Warp
program-owned account families. It still does not assign a semantic layout or
qualify a bridge route. A later semantic-layout slice may interpret fields only
when those meanings can be independently reproduced and fail closed under the
same evidence discipline.
