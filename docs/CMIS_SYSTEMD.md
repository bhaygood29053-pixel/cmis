# Managed CMIS gateway

Liquidity Scout can run the read-only CMIS HTTP gateway as a local systemd service instead of requiring a terminal to remain open.

## Install

From the Liquidity Scout repository, with the project virtualenv already created and the normal local `.env` containing `X1_NINJA_API_KEY`:

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

A production-style local stack should start the CMIS and Roberta bridge services before the MoltGrid listener:

```text
cmis-gateway.service       -> 127.0.0.1:8765
roberta-bridge.service     -> 127.0.0.1:8766
             \             /
              MoltGrid listener
```

Roberta remains the conversational/orchestration authority. X1 Scout delegates deterministic X1 market/risk work to CMIS. CMIS remains read-only and does not authorize signing, broadcast, custody, or execution.
