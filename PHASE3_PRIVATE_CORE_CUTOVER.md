# Phase 3 — CMIS Private-Core Cutover

Status: **COMPLETE**

The public repository owns CMIS transport and public contract surfaces. The
runtime implementation is required from the private facade contract
`cmis-private-core/v1`.

## Final public/private boundary

Public-owned surfaces:
- `liquidity_scout/cmis/__init__.py`
- `liquidity_scout/cmis/capabilities.py`
- `liquidity_scout/cmis/http.py`
- `liquidity_scout/cmis_private_core.py`

The public capability contract now owns the accepted runtime service and chain
identifiers. Default HTTP runtime construction loads `cmis-private-core`
lazily and validates the private service/chain surface against that public
contract.

There is **no public implementation fallback**. If `cmis-private-core` is
missing or contract-incompatible, default CMIS runtime construction fails
closed.

## Phase 3 validation evidence

Required-private-core split validation passed in ROBERTA workflow run
`33227923034` with:
- `CMIS_PRIVATE_CORE_REQUIRED=1`;
- protected CMIS implementation removed from the assembled public shell;
- `cmis-private-core==0.2.0` installed into the split runtime;
- ROBERTA -> X1 Scout -> CMIS HTTP -> private `RuntimeCMISGateway` completed;
- `PUBLIC_FALLBACK_USED=FALSE`.

The fallback-free CMIS public regression suite also passed in Liquidity Scout
Tests run `33227949785`.

## Safety state

Phase 3 changes no authority boundaries:
- ROBERTA owns orchestration/final synthesis.
- Chain Scouts interpret and investigate.
- CMIS owns deterministic verified facts/evidence/risk.
- Providers remain beneath CMIS.
- No execution, signing, broadcasting, custody, autonomous value movement, new
  fact authority, or new service promotion is introduced.

Protected implementation remains in public Git HEAD until the dedicated source
removal phase. Historical Git-object cleanup remains a separate later phase.

## Next phase

Phase 4 broadens split-runtime integration/CI coverage and operationalizes the
private-package validation path before public protected-source removal.
