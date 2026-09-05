# XDEX Extended Read-Only Structured Discovery v1

Status: implementation candidate under CMIS Issue #485.

## Purpose

This contract implements the direct machine-readable XDEX gaps identified by the accepted XDEX Network Gap Registry.

Contract:

`xdex_extended_readonly_structured_discovery/v1`

The accepted gap report concluded:

`browser_capture_required_now=false`

because the useful uncovered surfaces are already direct GET endpoints.

This contract therefore adds structured URL/query interpretation for exactly:

1. the deployed XDEX frontend quote alias;
2. the XDEX Oracle token-price endpoint;
3. the XDEX Oracle sell-quote endpoint.

It does not add browser automation.

## XDEX Web Discovery source boundary

The XDEX Web Discovery source now explicitly allows:

- `xdexdocs.gitbook.io`
- `api.xdex.xyz`
- `oracle.xdex.xyz`

This is an exact-host allowlist. No wildcard XDEX subdomain policy is introduced.

## Frontend quote alias

Endpoint:

`https://api.xdex.xyz/api/xdex/swap/quote`

Required query fields:

- `network`
- `token_in`
- `token_out`
- `token_in_amount`
- `is_exact_amount_in`

Optional:

- `slippage`
- `amm_config_address`

Validation:

- token identifiers must decode to 32-byte Base58 candidates;
- token pair must differ;
- amount must be positive and finite;
- exact-in flag must be literal `true` or `false`;
- config address, when present, must decode to a 32-byte Base58 candidate.

The structured layer records:

`route_config_verified=false`

even when a syntactically valid `amm_config_address` is supplied.

Existing live CMIS evidence compares this deployed frontend alias against the accepted research route:

`/api/xendex/swap/quote`

That comparison evidence is scoped. The v7 parser does not declare universal alias equivalence.

The original research route remains owned by:

`xdex_structured_discovery/v1`

and is intentionally unsupported by v7.

## XDEX Oracle token price

Endpoint:

`https://oracle.xdex.xyz/api/v1/token/price`

Two request modes are recognized.

### Exact token

`token_address=<32-byte Base58 candidate>`

Example shape:

```text
/api/v1/token/price?token_address=<TOKEN>
```

### All details

Exact request shape:

```text
/api/v1/token/price?all=true&details=true
```

The modes are mutually exclusive.

The parser rejects:

- token + all/details mixed together;
- partial all/details mode;
- non-literal boolean forms;
- extra parameters;
- duplicate parameters.

Recognition of either request shape does not verify:

- response correctness;
- token-price semantics;
- observation time;
- freshness;
- market-source independence;
- CMIS promotion eligibility.

The Oracle remains part of the XDEX source family.

## XDEX Oracle sell quote

Endpoint:

`https://oracle.xdex.xyz/api/v1/token/sell-quote`

Required:

- `token_address=<32-byte Base58 candidate>`
- `amount_in=<positive finite decimal>`

No additional parameter is accepted by this contract.

Existing scoped CMIS evidence establishes that for tested XENCAT/native-XNT cases:

`amount_out_quote`

matches a no-fee constant-product curve reference.

The structured result therefore preserves the known semantic scope as:

`no_fee_cp_curve_reference_for_tested_cases_only`

while explicitly retaining:

`fee_complete=false`
`slippage_adjusted=false`
`executable_quote=false`
`route_optimality_verified=false`
`fill_quality_verified=false`

The v7 parser does not promote the scoped live evidence into a universal Oracle contract.

## Execution boundary

These paths are not accepted by this contract:

- `/api/xendex/swap/prepare`
- `/api/xdex/swap/prepare`

They remain execution-adjacent exclusions under the XDEX gap registry.

The extended parser does not prepare, replay, sign, broadcast, or submit requests.

## Verification handoff

### Frontend quote alias

Candidate evidence maps back to:

- existing XDEX read-only quote transport/evidence;
- `tests/test_xdex_frontend_quote_route_live.py`;
- existing XDEX route/config/reserve/quote semantic verification.

### Oracle token price

Candidate evidence maps back to:

- `.github/workflows/xdex-oracle-price-evidence.yml`;
- existing CMIS identity/price/freshness gates where applicable.

### Oracle sell quote

Candidate evidence maps back to:

- `tests/test_xdex_output_slippage_semantics_live.py`;
- `docs/XDEX_OUTPUT_SLIPPAGE_RESEARCH.md`.

The handoff does not itself run those contracts.

## Truth state

Every supported v7 URL remains:

`discovery_state=DISCOVERED`
`xdex_extended_route_verified=true`
`provider_response_verified=false`
`frontend_alias_equivalence_verified=false`
`oracle_price_semantics_verified=false`
`oracle_sell_quote_semantics_verified=false`
`route_config_verified=false`
`web_claim_verified=false`
`cmis_verified=false`
`source_independence_verified=false`
`request_replay_authorized=false`
`public_service_promoted=false`
`scout_reliance_promoted=false`
`cmis_promotable=false`
`execution_authorized=false`

URL/query recognition proves syntax only.

## Non-goals

This contract does not:

- replace `XDEXReadOnlyProvider`;
- replace v5 XDEX structured discovery;
- establish universal frontend alias equivalence;
- treat Oracle as an independent market source;
- infer Oracle freshness;
- call swap prepare;
- launch a browser;
- replay requests;
- add arbitrary XDEX API access;
- prepare/sign/broadcast transactions;
- move value.

## Next decision after acceptance

After the three known direct gaps are structured, the next XDEX Web Discovery step should be a **coverage reconciliation**:

- confirm the gap registry has no remaining known useful direct read-only gap;
- determine whether XDEX UI-only surfaces expose any unique information that is material enough to justify a browser capture issue.

Browser capture should remain unnecessary unless a specific missing fact is first identified.
