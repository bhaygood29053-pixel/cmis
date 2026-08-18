# Liquidity Scout v0.12 / CMIS

Liquidity Scout is the migration codebase that houses the deterministic **Cross-Chain Market Intelligence Service (CMIS)**, X1/XDEX and Solana provider implementations, verification/evidence tooling, and the MoltGrid transport used to reach Roberta.

The project began as a paper-trading prototype and has evolved into a broader blockchain-intelligence service. **Live trading, wallet signing, custody, and autonomous value movement remain disabled.**

## Current milestone status

**Phase 10 — More Specialists / Providers is COMPLETE. Phase 11 — Controlled Execution is LOCKED / NOT STARTED.**

The CMIS Phase 10 Solana provider tracker was closed after the deterministic X1 regression suite and the read-only Solana production-runtime acceptance path were completed. The production-composition change was merged in PR #158, and the versioned Scout ↔ CMIS capability contract was merged in PR #152.

Current chain posture:

- **X1/XDEX:** mature deterministic market, tokenomics, risk, trade-verification, evidence, ranking/history, and bounded pre-trade analysis foundation.
- **Solana:** read-only CMIS foundation with exact-mint identity, canonical RPC tokenomics, bounded/partial market and risk evidence, provenance-safe observation history, and narrow same-source historical comparison.
- **Ethereum:** not promoted into the accepted runtime contract.

The machine-readable Scout ↔ CMIS eligibility boundary is documented in [`docs/CMIS_CAPABILITY_CONTRACT.md`](./docs/CMIS_CAPABILITY_CONTRACT.md). Detailed Phase 10 completion notes are in [`docs/PHASE_10_COMPLETION.md`](./docs/PHASE_10_COMPLETION.md).

## Architecture

```text
MoltGrid Signal
      ↓
Liquidity Scout transport / admission / duplicate protection
      ↓
Roberta — Oracle / Coordinator / normal user-facing voice
      ↓
Chain Scouts
  ├── X1 Scout
  └── Solana Scout
      ↓
CMIS
  ├── X1/XDEX providers
  └── Solana providers
```

Authority flows downward:

```text
Roberta → Chain Scout → CMIS → Chain Provider
```

Verified information flows upward:

```text
Chain Provider → CMIS → Chain Scout → Roberta
```

Roberta owns user intent, policy, coordination, and final synthesis. Chain Scouts own chain-specific planning and interpretation. CMIS owns deterministic freshness-sensitive facts, evidence, risk, and bounded pre-trade analysis. Providers own chain-specific transport and parsing.

Roberta and Chain Scouts do not reproduce provider/CMIS calculations to manufacture a second market fact.

## Machine-readable capability contract

CMIS publishes the deployed service boundary at:

```text
GET /v1/cmis/capabilities
```

The current manifest uses capability schema `1` and a versioned CMIS contract. Every known chain/service combination is explicitly classified as:

- `supported`
- `bounded`
- `partial`
- `unavailable`

Each record also includes `callable`, requirements, and limitations.

The shared Chain Scout CMIS client validates this manifest before a service POST. Missing, malformed, incompatible, or explicitly non-callable capabilities fail closed. `partial` and `bounded` services can remain callable, but their limitations are preserved and must not be upgraded by a Scout or by Roberta.

Roberta does **not** call provider APIs or the capability endpoint directly.

## Current Roberta-facing CMIS service surface

The shared service contract includes:

- `asset_lookup`
- `market_report`
- `rank`
- `historical_compare`
- `tokenomics`
- `risk_check`
- `pre_trade_check`
- `verification_evidence`

Availability is chain- and deployment-specific. The live capability manifest is authoritative; support on X1 must never be assumed to imply support on Solana.

## X1/XDEX market intelligence

CMIS can:

- search the XDEX pool catalog from X1.Ninja;
- resolve assets by symbol, token name, mint address, or pool address;
- reject ambiguous human-facing identifiers instead of silently selecting the wrong mint;
- aggregate provider-listed liquidity and volume across multiple pools;
- retrieve XNT reference pricing;
- independently inspect X1/XDEX on-chain evidence where implemented;
- distinguish provider coverage from independently verified on-chain coverage;
- answer asset questions without silently falling back to AGI or another default asset.

Example questions:

```text
What is the price of XNT?
Tell me about AGI.
What is the liquidity for X1X?
Find XENCAT.
What pools does THEO have?
```

### XDEX rankings

`xdex_rankings.py` uses the reusable market core and supports rankings for:

- 24-hour volume;
- liquidity;
- holders where provider semantics support the field;
- safety score;
- biggest 24-hour gainers;
- biggest 24-hour losers;
- trending activity.

`build_top50_xdex.py` can generate Top-50 XDEX ranking exports for deeper analysis. Generated CSV/JSON outputs are ignored by Git.

### X1 trade verification and verified activity

CMIS contains deterministic X1/XDEX verification paths that can independently evaluate provider trade candidates against X1 RPC evidence. Depending on available evidence, CMIS can verify transaction identity, recognized XDEX program participation, token-account deltas, pool-leg amounts, and BUY/SELL direction.

Provider observations remain candidates rather than automatic canonical truth. Missing or contradictory evidence fails closed.

CMIS also contains bounded program-scoped XDEX activity coverage logic. Program-scoped completeness must not be relabeled as global all-X1 DEX completeness unless the relevant program registry itself is proven exhaustive.

### Historical market intelligence

Liquidity Scout stores historical XDEX snapshots in SQLite and can compare current metrics with stored observations.

Supported historical periods include 24 hours, 7 days, and 30 days where enough observations have been collected. Supported X1 comparison metrics include price, liquidity, 24-hour volume, holders, and total supply when the underlying field is available under the current evidence contract.

Run one XDEX history snapshot with:

```bash
python snapshot_xdex_metrics.py
```

Historical comparisons report insufficient history rather than fabricating a baseline.

### Tokenomics and burn intelligence

Liquidity Scout includes tokenomics/burn tooling such as:

```text
agi_burn_scan.py
x1_burn_scan.py
x1_burn_scan_v2.py
```

Core tokenomics rules include:

- total supply must come from accepted evidence;
- mint and freeze authority status are chain facts where verified;
- burn totals require verified burn instructions/evidence;
- circulating supply is not guessed;
- market cap is not promoted as verified without verified circulating supply;
- FDV is not promoted as verified without a verified maximum supply;
- active mint authority requires issuance/mint tracking in addition to burn tracking.

## Deterministic risk and bounded pre-trade analysis

`risk_check` is deterministic and runtime-callable where the capability manifest permits it.

`pre_trade_check` is **analysis only**. On the accepted X1 path it can use already-verified evidence for trade notional, verified asset-wide liquidity, notional-to-liquidity ratio, explicit policy thresholds, and evidence freshness rules.

Advanced execution estimates remain unavailable unless a verified producer exists, including:

- slippage;
- price impact;
- route quality;
- bridge dependency;
- fees;
- transaction simulation.

Unavailable execution fields remain `null` with explicit reasons. CMIS never substitutes guessed percentages, routes, or fees.

Every current pre-trade result preserves the equivalent of:

```text
analysis_only = true
execution_authorized = false
```

A `PASS` means only that the deterministic checks actually performed did not produce a warning/block. It is not permission to trade.

## Solana read-only foundation

Phase 10 added Solana beneath the same CMIS contract rather than creating a second intelligence stack.

Accepted Solana components include:

- canonical `getAccountInfo(jsonParsed)` mint identity;
- SPL Token and Token-2022 program identity checks;
- canonical `getTokenSupply` total supply;
- mint/freeze authority evidence;
- optional `getTokenLargestAccounts` concentration evidence that is **not** treated as total holder count;
- Jupiter Price V3 source evidence when configured;
- Helius DAS indexed evidence when configured;
- DEX Screener pair-scoped market evidence;
- deterministic Jupiter ↔ DEX Screener price cross-check;
- deterministic RPC ↔ Helius supply cross-check;
- provenance-safe Solana observation history;
- narrow Jupiter same-source historical comparison;
- gated Solana `asset_lookup`, `tokenomics`, `market_report`, `risk_check`, and `historical_compare` behavior.

Solana production composition is disabled by default. Enable it only through deployment environment configuration:

```text
CMIS_SOLANA_PROVIDER_ENABLED=1
SOLANA_RPC_URL=
JUPITER_API_KEY=
HELIUS_API_KEY=
CMIS_SOLANA_PRICE_MAX_RELATIVE_DIFFERENCE=
CMIS_SOLANA_SUPPLY_MAX_INDEX_SLOT_LAG=
CMIS_SOLANA_HISTORY_MAX_DISTANCE_SECONDS=
CMIS_SOLANA_OBSERVATION_DB=
```

Missing optional providers or policies fail closed at the dependent service. Secrets are never request parameters or returned provenance.

Exact mint identity is required where promoted. Pair-scoped DEX values are not silently relabeled as Solana-wide totals, and provider labels such as verified/organic/safe remain source evidence rather than Roberta's final risk decision.

## Verification evidence

CMIS includes a sanitized, content-addressed verification-evidence path:

```text
fact-specific verifier
  ↓
sanitized verification envelope
  ↓
content-addressed evidence ledger
  ↓
exact lookup
  ↓
CMIS
  ↓
Chain Scout / Roberta
```

Roberta does not submit raw verifier/provider objects, choose persistence paths, or reconstruct verification state. `AGREEMENT`, `CONFLICT`, and `INSUFFICIENT_EVIDENCE` remain explicit evidence outcomes.

## MoltGrid / Roberta runtime

The current **Roberta-first production listener** is:

```bash
python -m liquidity_scout.integrations.moltgrid_roberta
```

It preserves MoltGrid transport/admission, reply linkage, and duplicate protection while routing admitted supported questions to Roberta. Roberta is the sole normal user-facing conversational voice.

When the MoltGrid simple-only policy is enabled, concise questions are admitted while long structured reports, raw evidence dumps, code, and other formatting-heavy requests are declined with a fixed interface-limitation response. Replies are rendered as MoltGrid-safe plain text.

If Roberta is unavailable, the user-facing path returns a short availability message rather than exposing the legacy Liquidity Scout router or raw CMIS output.

The older direct package integration remains available for deliberate diagnostics/rollback:

```bash
python -m liquidity_scout.integrations.moltgrid
```

`moltgrid_signal_v12_ollama.py` is legacy implementation code retained for diagnostics/rollback; it is not the preferred user-facing production architecture.

## Managed local services

The intended local managed topology is:

```text
CMIS        127.0.0.1:8765
  ↓
Roberta     127.0.0.1:8766
  ↓
MoltGrid listener
```

The repository includes systemd deployment/install support for CMIS and for the MoltGrid dependency chain. The listener can wait for both CMIS and Roberta health endpoints before starting. No secrets are stored in unit files or Git.

See:

```text
docs/CMIS_CAPABILITY_CONTRACT.md
docs/CMIS_SYSTEMD.md
SCOUT_CMIS_INTEGRATION_CONTRACT.md
ROBERTA_INTEGRATION_CONTRACT.md
```

## Installation

From WSL2 or Linux:

```bash
git clone https://github.com/bhaygood29053-pixel/liquidity-scout.git
cd liquidity-scout
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Current core Python requirements include:

```text
requests
python-dotenv
```

Never commit secrets. API keys belong in local environment/configuration files excluded from Git.

For X1/XDEX operation, configure the public AgentID wallet and X1.Ninja API key as needed:

```text
AGENT_WALLET=YOUR_PUBLIC_X1_WALLET_ADDRESS
X1_NINJA_API_KEY=YOUR_X1_NINJA_API_KEY
X1_RPC_URL=https://rpc.mainnet.x1.xyz
```

The wallet address is public. **Never place a seed phrase, private key, or signing key in `.env` or the repository.**

## Safety boundary

Liquidity Scout/CMIS is an intelligence system, not an autonomous execution engine.

It does **not**:

- sign wallet transactions;
- store/request a private key or seed phrase as part of CMIS intelligence;
- execute live swaps;
- autonomously move funds;
- treat AI-generated text as verified market data;
- silently promote partial/program-scoped evidence into global completeness.

Human approval in Roberta Phase 9 is a review boundary, not a reusable signing credential.

**Phase 11 controlled execution remains planned/locked and has not started.** Any future execution work requires a new explicit milestone and separate deterministic safeguards.

## Roberta integration

Roberta is the top-level Oracle/Agent Coordinator. X1 Scout and Solana Scout live above CMIS and invoke the shared CMIS client; they are not provider implementations inside this repository.

The authoritative integration boundary is [`ROBERTA_INTEGRATION_CONTRACT.md`](./ROBERTA_INTEGRATION_CONTRACT.md), with service eligibility documented in [`docs/CMIS_CAPABILITY_CONTRACT.md`](./docs/CMIS_CAPABILITY_CONTRACT.md) and enforced by the live `/v1/cmis/capabilities` manifest.

Roberta must preserve CMIS status, provenance, confidence, warnings, and unavailable fields. It may translate deterministic evidence into user-friendly language, but it must not rewrite a partial/unavailable fact into a verified one.

## Repository structure

Key paths include:

```text
liquidity_scout/cmis/                     Shared deterministic CMIS service layer
liquidity_scout/providers/x1/             X1/XDEX provider and verification evidence
liquidity_scout/providers/solana/         Solana read-only provider foundation
liquidity_scout/integrations/             MoltGrid transport/Roberta integration
docs/CMIS_CAPABILITY_CONTRACT.md          Machine-readable service eligibility docs
docs/CMIS_PRODUCT_ROADMAP.md              Long-term CMIS product/premium roadmap
docs/PHASE_10_COMPLETION.md               Accepted Phase 10 status/boundaries
ROBERTA_INTEGRATION_CONTRACT.md           Roberta ↔ Chain Scout ↔ CMIS boundary
SCOUT_CMIS_INTEGRATION_CONTRACT.md        Chain Scout ↔ CMIS boundary
deployment/                               Example deployment files
historical_metrics.py                     Historical comparison engine
snapshot_xdex_metrics.py                  XDEX snapshot collector
xdex_rankings.py                          XDEX ranking support
moltgrid_signal_v12_ollama.py             Legacy diagnostic/rollback listener
```

Runtime databases, generated ranking exports, local backups, virtual environments, caches, logs, and `.env` secrets are excluded through `.gitignore`.

## Development status

### Working now

- reusable XDEX catalog discovery and asset resolution;
- XDEX rankings and market reporting;
- X1 RPC supply/authority verification;
- deterministic X1 trade verification and bounded verified-activity coverage;
- deterministic risk and bounded pre-trade analysis;
- CMIS HTTP/runtime service composition and capability discovery;
- persisted verification evidence;
- historical XDEX snapshots/comparisons;
- managed CMIS/Roberta/MoltGrid integration boundaries;
- Phase 10 Solana read-only provider/runtime foundation;
- read-only Solana live acceptance in GitHub Actions.

### Milestone boundary

Phase 10 is complete. Remaining X1 evidence-completeness and optional provider rollout work are separate follow-up tracks. They do **not** silently begin Phase 11.

The long-term product direction remains in [`docs/CMIS_PRODUCT_ROADMAP.md`](./docs/CMIS_PRODUCT_ROADMAP.md). Future milestones should use new issue/phase trackers so completed Phase 10 boundaries are not silently expanded.

## Git workflow

Use small, tested milestone commits rather than allowing unrelated changes to accumulate.

Before a major refactor or new service:

```bash
git status
git add <intentional-files>
git diff --cached --check
git commit -m "Describe the tested milestone"
git push
```

Do not use `git add .` when runtime databases, generated files, backups, or local secrets may be present.

---

**CMIS verifies what is happening now. Chain Scouts interpret chain-specific evidence. Roberta coordinates and explains.**
