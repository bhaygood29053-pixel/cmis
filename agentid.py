import requests

VERIFY_URL = "https://agentid-app.vercel.app/api/verify"

class AgentIDError(RuntimeError):
    pass

def verify_agent(wallet: str, timeout: int = 12) -> dict:
    """Read-only AgentID verification. No signing and no wallet secret needed."""
    if not wallet:
        return {"configured": False, "verified": False, "message": "AGENT_WALLET not set"}
    r = requests.get(VERIFY_URL, params={"wallet": wallet}, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return {
        "configured": True,
        "verified": bool(data.get("verified")),
        "wallet": wallet,
        "raw": data,
    }
