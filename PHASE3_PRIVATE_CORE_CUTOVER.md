# Phase 3 — CMIS Private-Core Cutover

Status: **IN PROGRESS**

The public repository now owns transport and public contract surfaces. Protected implementation is consumed through the private facade contract `cmis-private-core/v1`.

## Public-owned surfaces

- `liquidity_scout/cmis/__init__.py`
- `liquidity_scout/cmis/capabilities.py`
- `liquidity_scout/cmis/http.py`
- `liquidity_scout/cmis_private_core.py`

The HTTP transport no longer imports `RuntimeCMISGateway` or gateway chain constants directly. It receives those values through `liquidity_scout.cmis_private_core.load_runtime_contract()`.

## Migration-only fallback

Until split validation is complete, the adapter may fall back to the existing public implementation so the public repository remains independently testable.

That fallback is not the target production architecture.

Production cutover requires:

`CMIS_PRIVATE_CORE_REQUIRED=1`

With that flag enabled, an absent or incompatible private core fails closed.

## Removal gate

Do not delete protected CMIS implementation from public HEAD until all of the following pass:

1. private distribution build and doctor;
2. public HTTP/capability tests using `cmis-private-core/v1`;
3. evidence, verification, risk, history, provider, Instant X1 Scan, and runtime tests across the split;
4. ROBERTA -> Scout -> CMIS integration validation;
5. required-private-core mode with no public fallback.

Historical Git cleanup is a separate post-cutover operation.
