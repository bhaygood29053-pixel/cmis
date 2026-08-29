# Phase 6 — Historical Git Cleanup and Migration Closure

Status: **FINAL VALIDATION**

Phase 6 rewrote the active public CMIS branch/tag history to remove protected
CMIS implementation paths from every reachable public ref while preserving the
public repository's branch/tag structure.

## Rewritten history

Historical cleanup workflow:
- Actions run `33252206849` — **SUCCESS**
- pre-rewrite ref-map artifact: `phase6-cmis-pre-rewrite-refs`
  - artifact id: `9714704479`
  - digest: `sha256:5e29f8ce9cb8e3e737ec1ffe62ca778a7dd7a47d1cd36bf20fd30082abb385e1`
- post-rewrite ref-map artifact: `phase6-cmis-post-rewrite-refs`
  - artifact id: `9714708892`
  - digest: `sha256:676f7790faede87e225003d8606e08745758d19543f5d9af6930336295ebdefa`

The rewrite removed the 35 Phase 5 protected CMIS implementation modules plus
two historical-only protected modules discovered by the all-ref verifier:
- `liquidity_scout/cmis/xdex_direct_candidate_comparison.py`
- `liquidity_scout/cmis/xdex_direct_quote_comparator.py`

The invariant enforced across every rewritten branch/tag was that the public
`liquidity_scout/cmis` Python boundary may contain only:
- `__init__.py`
- `capabilities.py`
- `http.py`

The rewrite gate verified the pre-rewrite main commit was no longer reachable
from rewritten local refs, rejected any ref retaining another CMIS Python
implementation module, force-pushed the rewritten refs, and verified the remote
ref count was preserved.

## Steady-state public boundary

The public CMIS package no longer eagerly imports protected implementation. It
exposes stable public service/chain identifiers and resolves legacy runtime
symbols only through the required private-core adapter.

Migration-era public reconstruction from protected public commits was removed
from normal tests. The Solana manual verification workflows now stop at the
public provider/deployment boundary instead of rebuilding private CMIS code from
historical public commits.

The normal public test workflow now verifies:
- no protected CMIS Python implementation remains in current public HEAD;
- `cmis-private-core` remains mandatory;
- missing private core fails closed;
- no public fallback exists;
- execution authorization remains false.

Closure-branch public-boundary test: Actions run `33252468519` — **SUCCESS**.

## Safety boundary

The authority chain remains:

**User -> ROBERTA -> Chain Scout -> CMIS -> Chain Provider**

No execution, signing, broadcasting, custody, autonomous value movement, new
fact authority, or new service promotion is authorized by this migration.

## Important limitation

This rewrite removes protected paths from the public repository's active
branch/tag history. It cannot revoke copies already cloned, forked, cached, or
downloaded, and Git hosting infrastructure may retain unreachable objects for
some period after refs are rewritten.

Phase 6 is complete once this closure state is merged to `main` and the same
public-boundary test passes from merged `main`.
