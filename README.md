# Liquidity Scout v0.12

Liquidity Scout is an X1/XDEX market-intelligence agent that monitors MoltGrid Signal, resolves assets across the XDEX catalog, retrieves verified market data, builds rankings and historical comparisons, and uses AI to explain verified facts without inventing market data.

The project began as a paper-trading prototype and has evolved into a broader X1 market-intelligence service. **Live trading and wallet signing remain disabled.**

## Current capabilities

### XDEX market intelligence

Liquidity Scout can:

- search the full XDEX pool catalog from X1.Ninja;
- resolve assets by symbol, token name, mint address, or pool address;
- aggregate liquidity and volume across multiple pools for the same asset;
- identify the deepest matching pool for price-oriented metrics;
- retrieve XNT pricing using X1.Ninja's XNT reference data;
- answer asset questions without silently falling back to AGI when another asset was requested.

Example questions:

```text
What is the price of XNT?
Tell me about AGI.
What is the liquidity for X1X?
Find XENCAT.
What pools does THEO have?
```

### XDEX rankings

`xdex_rankings.py` aggregates pool data into one record per asset and supports rankings for:

- 24-hour volume;
- liquidity;
- holders;
- safety score;
- biggest 24-hour gainers;
- biggest 24-hour losers;
- trending activity using 1-hour transaction counts when available, with 1-hour volume as a fallback.

Example questions:

```text
What are the top 10 tokens on XDEX?
Top 5 by liquidity.
What tokens are trending on X1.Ninja?
Show me the biggest gainers.
Where does AGI rank by volume?
Is AGI in the top 50?
```

`build_top50_xdex.py` can also generate Top-50 XDEX ranking exports for deeper analysis. Generated CSV/JSON outputs are intentionally ignored by Git.

## Historical market intelligence

Liquidity Scout now stores historical XDEX snapshots in SQLite and can compare current metrics with stored observations.

Supported historical periods:

- 24 hours;
- 7 days;
- 30 days.

Supported comparison metrics include:

- price;
- liquidity;
- 24-hour volume;
- holders;
- total supply.

Example questions:

```text
Has AGI liquidity fallen more than 30% this week?
Did X1X volume increase 20% in 24 hours?
Are AGI holders down 5% this month?
Has AGI price dropped 10% in 7 days?
```

Historical comparisons only become available after enough snapshots have been collected for the requested period. Liquidity Scout reports when the history window is not yet mature instead of fabricating a comparison.

### Snapshot collector

Run one XDEX history snapshot with:

```bash
python snapshot_xdex_metrics.py
```

The collector is designed to be scheduled periodically, such as hourly, so the local history database grows over time.

## Tokenomics and burn intelligence

Liquidity Scout includes dedicated tokenomics/burn tooling:

```text
agi_burn_scan.py
x1_burn_scan.py
x1_burn_scan_v2.py
```

These scanners inspect successful X1 transactions for standard token burn instructions and cache processed data locally in SQLite databases.

Current tokenomics principles:

- total supply is retrieved from verified X1 RPC data;
- mint and freeze authority status are treated as on-chain facts;
- burn totals are derived from verified burn instructions;
- circulating supply is not guessed when reliable data is unavailable;
- market cap is not presented as verified without verified circulating supply;
- FDV is not presented as verified without a verified maximum supply;
- tokens with active mint authority require issuance/mint tracking in addition to burn tracking.

Local runtime databases are ignored by Git.

## AI intelligence layer

Liquidity Scout uses a hybrid architecture:

1. **Deterministic data layer** retrieves and calculates XDEX/X1 facts.
2. **DeepSeek** can provide cloud-based analysis when configured.
3. **Ollama/Qwen** provides a local fallback reasoning layer.

The AI layer is intended to explain and interpret verified data. It is not the source of truth for price, liquidity, supply, rankings, burns, or other live market facts.

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

The current main listener is:

```text
moltgrid_signal_v12_ollama.py
```

It:

- watches MoltGrid Signal replies;
- detects questions directed to Liquidity Scout;
- resolves requested XDEX assets;
- retrieves current market facts;
- routes ranking and historical questions to deterministic engines;
- optionally uses DeepSeek or Ollama for grounded explanations;
- reuses conversation state so previously answered messages are not repeatedly processed.

Run it with:

```bash
python moltgrid_signal_v12_ollama.py
```

## Sentinel development tooling

The repository includes lightweight development and diagnostics tools:

```text
sentinel_diagnostics.sh
sentinel_issues.py
development/issues.json
```

Run diagnostics with:

```bash
bash sentinel_diagnostics.sh
```

The issue utility maintains a small development backlog under `development/`.

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

Current Python requirements are intentionally small:

```text
requests
python-dotenv
```

## Configuration

At minimum, configure the public AgentID wallet and X1.Ninja API key in `.env`:

```text
AGENT_WALLET=YOUR_PUBLIC_X1_WALLET_ADDRESS
X1_NINJA_API_KEY=YOUR_X1_NINJA_API_KEY
X1_RPC_URL=https://rpc.mainnet.x1.xyz
```

The wallet address is public. **Never place a seed phrase, private key, or signing key in `.env` or the repository.**

## Safety boundary

Liquidity Scout v0.12 is currently an intelligence system, not an autonomous execution engine.

It does **not**:

- sign wallet transactions;
- store or request a private key or seed phrase;
- execute live swaps;
- autonomously move funds;
- treat AI-generated text as verified market data.

Trading/execution should remain a separate, human-approved capability until the intelligence, risk, and service layers have been fully tested.

## Repository structure

Key files currently include:

```text
moltgrid_signal_v12_ollama.py   Main MoltGrid/XDEX intelligence listener
config.py                       Environment-based configuration
xdex_rankings.py                Asset aggregation and ranking engine
historical_metrics.py           Historical comparison engine
snapshot_xdex_metrics.py        XDEX snapshot collector
build_top50_xdex.py             Top-50 asset export builder
agi_burn_scan.py                AGI burn scanner
x1_burn_scan.py                 Generic X1 token burn scanner
x1_burn_scan_v2.py              Extended period/cached burn scanner
sentinel_diagnostics.sh         Service/project diagnostics
sentinel_issues.py              Development issue utility
development/issues.json         Current development issue backlog
```

Runtime databases, generated ranking exports, local backups, virtual environments, caches, logs, and `.env` secrets are excluded through `.gitignore`.

## Development status

### Working now

- XDEX catalog discovery and asset resolution;
- live XDEX/X1 market-data retrieval;
- MoltGrid Signal question/response loop;
- global and asset-specific XDEX rankings;
- hourly-compatible historical snapshot collection;
- 24h/7d/30d historical comparison logic;
- AGI/X1 token burn-scanning tools;
- verified supply and authority checks;
- DeepSeek reasoning with local Ollama fallback;
- development diagnostics and issue tracking.

### Next major phases

1. Finish and harden tokenomics services, including mint/net-issuance tracking where required.
2. Build a deterministic Liquidity Scout Risk Engine and Scout Score.
3. Refactor the main listener into smaller service/integration modules.
4. Expose structured Liquidity Scout data through an API/service layer.
5. Connect Roberta as the X1 Oracle/coordinator to Liquidity Scout as a specialist service.
6. Add alert automation and threshold monitoring.
7. Consider controlled trading/execution only after the intelligence and risk layers are proven.

## Git workflow

Use small, tested milestone commits rather than allowing many unrelated changes to accumulate.

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

**Liquidity Scout is being developed as a deterministic X1/XDEX intelligence foundation first, with AI used for explanation and orchestration rather than as a substitute for verified market data.**
