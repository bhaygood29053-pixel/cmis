import requests

BASE_URL = "http://localhost:11434"
MODEL = "qwen3:4b"

tags = requests.get(f"{BASE_URL}/api/tags", timeout=5)
tags.raise_for_status()
models = {
    (m.get("name") or m.get("model"))
    for m in tags.json().get("models", [])
}

assert MODEL in models, f"{MODEL} is not installed. Installed: {sorted(models)}"

payload = {
    "model": MODEL,
    "messages": [
        {
            "role": "system",
            "content": (
                "You are Liquidity Scout. Answer clearly and concisely. "
                "Do not invent live token market data."
            ),
        },
        {
            "role": "user",
            "content": "What is slippage in DeFi?",
        },
    ],
    "stream": False,
    "think": False,
    "options": {
        "temperature": 0.2,
        "num_predict": 180,
    },
}

response = requests.post(
    f"{BASE_URL}/api/chat",
    json=payload,
    timeout=120,
)
response.raise_for_status()

answer = (
    response.json()
    .get("message", {})
    .get("content", "")
    .strip()
)

assert answer, "Ollama returned an empty answer."

print("Ollama v12 connectivity: PASS")
print()
print(answer)
