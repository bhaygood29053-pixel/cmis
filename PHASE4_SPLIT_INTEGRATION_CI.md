# Phase 4 — CMIS Split Integration / CI

Status: **COMPLETE**

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

## Checkpoint 1

The initial Phase 4 cross-repository gate passed in ROBERTA Actions run
`33228563613`.

CMIS-specific proof included:
- protected CMIS implementation absent from the staged public shell before private install;
- `cmis-private-core==0.2.0` supplied the runtime;
- public/private service and chain surfaces matched exactly;
- CMIS capability handshake succeeded through authenticated HTTP;
- unauthenticated capability access failed closed;
- X1 Scout reached the private CMIS runtime;
- Solana provider-gate isolation did not fall through to X1;
- `PUBLIC_FALLBACK_USED=FALSE`;
- `EXECUTION_AUTHORIZED=FALSE`.

## Source-removal gate

Phase 4 does not remove protected CMIS implementation from public Git HEAD.
The split integration gate is now green and stable on merged `main`; controlled
public-source removal belongs to the next migration phase.

No execution, signing, broadcasting, custody, value movement, new fact source,
or new service promotion is authorized.


## Final Phase 4 evidence

Phase 4 completion is proven by merged-main ROBERTA Actions run
`33249158272` — **SUCCESS** — against CMIS baseline
`45551d112e0779343c0d0e50d0d2631efc88f76c`.

The source-stripped/private-core gate exercised every promoted CMIS runtime
service through authenticated HTTP and recorded
`PHASE4_PROMOTED_CMIS_SERVICE_SURFACE=PASS`,
`PUBLIC_FALLBACK_USED=FALSE`, and `EXECUTION_AUTHORIZED=FALSE`.

CMIS main regression run `33228683303` and ROBERTA merged-main regression run
`33249158273` both passed.

The Phase 4 readiness gate for the next migration phase was satisfied.
Phase 5 subsequently removed the protected CMIS implementation from current
public HEAD; historical Git cleanup remains separate.
