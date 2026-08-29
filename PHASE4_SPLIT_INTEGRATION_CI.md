# Phase 4 — CMIS Split Integration / CI

Status: **IN PROGRESS**

Phase 4 hardens the mandatory CMIS private-engine boundary before protected
public implementation is removed.

## Primary gates

1. The staged public shell must exclude protected `liquidity_scout/cmis`
   implementation before the private wheel is installed.
2. `cmis-private-core==0.2.0` must provide the protected runtime implementation.
3. The private facade service/chain surface must exactly match the public
   capability contract.
4. CMIS capability and authenticated HTTP transport must work across the split.
5. ROBERTA -> X1 Scout -> CMIS must complete through the private runtime.
6. Solana remains bounded by its explicit provider gate; no X1 fallthrough is allowed.
7. The public fallback remains absent.
8. CI must emit machine-readable split-validation evidence.

## Source-removal gate

Phase 4 does not remove protected CMIS implementation from public Git HEAD.
Source removal is a later phase and remains blocked until the Phase 4 split
integration gate is green and repeatable.

No execution, signing, broadcasting, custody, value movement, new fact source,
or new service promotion is authorized.
