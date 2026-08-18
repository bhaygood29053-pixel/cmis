# Liquidity Scout v0.12

Liquidity Scout is a deterministic market-intelligence system for X1/XDEX with a shared Cross-Chain Market Intelligence Service (CMIS) foundation. It resolves assets, retrieves and verifies market/on-chain evidence, builds rankings and historical comparisons, performs deterministic risk analysis, and lets Roberta or other integrations explain those facts without inventing live market data.

The project began as a paper-trading prototype and has evolved into a broader blockchain-intelligence service. **Live trading, wallet signing, custody, and autonomous value movement remain disabled.**

## Current milestone status

**CMIS Phase 10 — Solana Provider read-only foundation is COMPLETE.**

The Phase 10 tracker was closed after both the full Liquidity Scout/X1 regression suite and a read-only Solana production-runtime live acceptance passed. The final production-composition change was merged in PR #158.

Current chain posture:

- **X1/XDEX:** mature deterministic market, tokenomics, risk, trade-verification, evidence, and pre-trade analysis foundation.
- **Solana:** read-only CMIS foundation with exact-mint identity, canonical RPC tokenomics, bounded/partial market and risk evidence, provenance-safe observation history, and narrow same-source historical comparison.
- **Ethereum:** not yet promoted into the accepted runtime contract.

The machine-readable Scout ↔ CMIS eligibility boundary is documented in [`docs/CMIS_CAPABILITY_CONTRACT.md`](./docs/CMIS_CAPABILITY_CONTRACT.md).

Detailed Phase 10 completion notes are in [`docs/PHASE_10_COMPLETION.md`](./docs/PHASE_10_COMPLETION.md).

## Architecture

```text
User / Signal / Agent
        |
        v
Liquidity Scout / Roberta
        |
        v
       CMIS
        |
   +----+-------------------+
   |                        |
   v                        v
X1/XDEX providers      Solana providers
   |                        |
   v                        v
verified evidence      bounded read-only evidence
```

CMIS is the deterministic evidence authority. Roberta and other AI layers may explain CMIS results, but they do not become the source of truth for price, liquidity, supply, trade direction, risk facts, or chain state.

## Current capabilities

### XDEX market intelligence

Liquidity Scout can:

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

`xdex_rankings.py` uses the reusable Liquidity Scout market core and supports rankings for:

- 24-hour volume;
- liquidity;
- holders where provider semantics support the field;
- safety score;
- biggest 24-hour gainers;
- biggest 24-hour losers;
- trending activity.

`build_top50_xdex.py` can generate Top-50 XDEX ranking exports for deeper analysis. Generated CSV/JSON outputs are ignored by Git.

### X1 trade verification and verified activity

CMIS contains deterministic X1/XDEX verification paths that can independently evaluate provider trade candidates against X1 RPC evidence. Depending on the evidence available, CMIS can verify transaction identity, recognized XDEX program participation, token-account deltas, pool-leg amounts, and BUY/SELL direction.

Provider observations remain candidates rather than automatic canonical truth. Missing or contradictory evidence fails closed.

CMIS also contains bounded program-scoped XDEX activity coverage logic. Program-scoped completeness must not be relabeled as global all-X1 DEX completeness unless the relevant program registry itself is proven exhaustive.

### Historical market intelligence

Liquidity Scout stores historical XDEX snapshots in SQLite and can compare current metrics with stored observations.

Supported historical periods include 24 hours, 7 days, and 30 days where enough observations have been collected.

Supported X1 comparison metrics include price, liquidity, 24-hour volume, holders, and total supply when the underlying field is available under the current evidence contract.

Run one XDEX history snapshot with:

```bash
python snapshot_xdex_metrics.py
```

Historical comparisons report insufficient history instead of fabricating a baseline.

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

### Deterministic risk and pre-trade analysis

CMIS now has a deterministic risk surface and bounded X1 pre-trade analysis. The pre-trade path is **analysis only** and does not authorize execution.

Slippage, route quality, transaction simulation, signing, broadcasting, and value movement remain unavailable unless separately implemented and explicitly promoted in the capability contract.

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

Solana is disabled by default in production runtime configuration. Enable only through deployment environment configuration:

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

Missing optional providers or policies fail closed at the dependent service. Secrets are never part of request parameters or returned provenance.

## AI intelligence layer

Liquidity Scout uses a hybrid architecture:

1. **Deterministic CMIS/market layer** retrieves, verifies, normalizes, and classifies evidence.
2. **Roberta / cloud reasoning** can explain and coordinate verified results when configured.
3. **Ollama/Qwen** can provide a local fallback reasoning layer.

AI-generated text is interpretation, not verified chain truth.

Optional AI environment variables include:

```text
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:4b-instruct
```

Never commit API keys to the repository. Keep secrets in `.env`.

## MoltGrid Signal listener

The canonical Liquidity Scout runtime entrypoint is:

```bash
python -m liquidity_scout.integrations.moltgrid
```

For normal repository operation:

```bash
bash run_liquidity_scout.sh
```

`run_liquidity_scout.sh` uses `.venv/bin/python` when present and otherwise falls back to `python3`.

The legacy `moltgrid_signal_v12_ollama.py` remains in the repository during the incremental refactor, but it is not the canonical operator entrypoint.

## CMIS runtime

CMIS exposes a structured service contract and a machine-readable capability manifest. The runtime composition includes the accepted X1 services plus gated Solana read-only services.

See:

```text
docs/CMIS_CAPABILITY_CONTRACT.md
docs/CMIS_SYSTEMD.md
SCOUT_CMIS_INTEGRATION_CONTRACT.md
ROBERTA_INTEGRATION_CONTRACT.md
```

The capability contract is authoritative for whether a chain/service combination is supported, bounded, partial, or unavailable.

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

## Configuration

For X1/XDEX operation, configure the public AgentID wallet and X1.Ninja API key in `.env` as needed:

```text
AGENT_WALLET=YOUR_PUBLIC_X1_WALLET_ADDRESS
X1_NINJA_API_KEY=YOUR_X1_NINJA_API_KEY
X1_RPC_URL=https://rpc.mainnet.x1.xyz
```

The wallet address is public. **Never place a seed phrase, private key, or signing key in `.env` or the repository.**

## Safety boundary

Liquidity Scout is an intelligence system, not an autonomous execution engine.

It does **not**:

- sign wallet transactions;
- store or request a private key or seed phrase as part of CMIS intelligence;
- execute live swaps;
- autonomously move funds;
- treat AI-generated text as verified market data;
- silently promote partial/program-scoped evidence into global completeness.

Any future trading/execution capability must remain a separate, explicit, human-approved boundary until separately designed, tested, and promoted.

## Roberta integration

Roberta is the higher-level Oracle/Agent Coordinator. Liquidity Scout and chain-specific Scouts remain independently testable specialist layers that consume CMIS evidence.

The authoritative integration boundary is documented in [`ROBERTA_INTEGRATION_CONTRACT.md`](./ROBERTA_INTEGRATION_CONTRACT.md), with service eligibility documented in [`docs/CMIS_CAPABILITY_CONTRACT.md`](./docs/CMIS_CAPABILITY_CONTRACT.md).

Roberta must preserve CMIS status, provenance, confidence, warnings, and unavailable fields. It may translate deterministic evidence into user-friendly language, but it must not rewrite a partial/unavailable fact into a verified one.

## Repository structure

Key paths include:

```text
liquidity_scout/cmis/                     Shared deterministic CMIS service layer
liquidity_scout/providers/x1/             X1/XDEX provider and verification evidence
liquidity_scout/providers/solana/         Solana read-only provider foundation
liquidity_scout/integrations/moltgrid.py  Canonical MoltGrid integration entrypoint
docs/CMIS_CAPABILITY_CONTRACT.md          Machine-readable service eligibility contract docs
docs/CMIS_PRODUCT_ROADMAP.md              Long-term CMIS product/premium roadmap
docs/PHASE_10_COMPLETION.md               Accepted Phase 10 status and boundaries
ROBERTA_INTEGRATION_CONTRACT.md           Roberta ↔ Liquidity Scout/CMIS boundary
SCOUT_CMIS_INTEGRATION_CONTRACT.md        Chain Scout ↔ CMIS boundary
run_liquidity_scout.sh                    Canonical repository launcher
deployment/                               Example deployment files
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
- MoltGrid/Roberta integration boundaries;
- Phase 10 Solana read-only provider/runtime foundation;
- read-only Solana live acceptance in GitHub Actions.

### Milestone boundary

Phase 10 is complete. This documentation update does **not** begin Phase 11 or enable additional execution authority.

The long-term product direction remains in [`docs/CMIS_PRODUCT_ROADMAP.md`](./docs/CMIS_PRODUCT_ROADMAP.md). Future work should use a new issue/phase tracker so completed Phase 10 boundaries are not silently expanded.

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

**Liquidity Scout is being developed as a deterministic cross-chain intelligence foundation first, with AI used for explanation and orchestration rather than as a substitute for verified evidence.**
