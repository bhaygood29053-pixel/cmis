# Managed CMIS gateway

CMIS can run its read-only HTTP gateway as a local systemd service instead of requiring a terminal to remain open.

The repository's Python package namespace remains `liquidity_scout` for compatibility, so the existing module entry points are intentionally unchanged.

## Install

From the **CMIS repository**, with the project virtualenv already created and the normal local `.env` containing any required provider configuration such as `X1_NINJA_API_KEY`:

```bash
bash scripts/install_cmis_systemd.sh
```

The installer:

- runs the gateway as the current non-root user;
- binds only to `127.0.0.1:8765`;
- uses the repository virtualenv and working directory;
- keeps provider secrets in the existing local `.env` rather than copying them into Git or the systemd unit;
- enables automatic start and `Restart=always` recovery;
- refuses to kill an unrelated process already using port 8765;
- waits up to 30 seconds for `/healthz` before declaring startup successful.

## Service operations

```bash
systemctl status cmis-gateway.service
sudo systemctl restart cmis-gateway.service
journalctl -u cmis-gateway.service -n 50 --no-pager
curl -fsS http://127.0.0.1:8765/healthz
```

After pulling CMIS code updates, restart the service so the managed process loads the new code:

```bash
git pull --ff-only origin main
sudo systemctl restart cmis-gateway.service
```

## Local dependency chain

A production-style local stack starts the CMIS and Roberta bridge services before the MoltGrid listener:

```text
cmis-gateway.service       -> 127.0.0.1:8765
roberta-bridge.service     -> 127.0.0.1:8766
             \             /
              MoltGrid listener
```

The MoltGrid listener may still carry the historical `liquidity-scout.service` unit name for compatibility. That service name does not change the canonical project architecture or CMIS repository identity.

Roberta remains the conversational/coordinating authority. Chain Scouts delegate deterministic chain market/risk/evidence work to CMIS. CMIS remains read-only and does not authorize signing, broadcasting, custody, trading, or execution.
