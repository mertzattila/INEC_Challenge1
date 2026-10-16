"""How much of your OpenRouter credit is left.

    python budget.py            # prints spent / limit / remaining
    from budget import remaining; remaining()["remaining"]
"""
import json
import os
import urllib.request


def remaining(api_key=None):
    """Return {"limit": float, "spent": float, "remaining": float} in US dollars."""
    key = api_key or os.environ["OPENROUTER_API_KEY"]
    req = urllib.request.Request("https://openrouter.ai/api/v1/key",
                                 headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())["data"]
    spent = data.get("usage", 0.0) + (data.get("byok_usage", 0.0) if data.get("include_byok_in_limit") else 0.0)
    return {"limit": data.get("limit"), "spent": spent, "remaining": data.get("limit_remaining")}


if __name__ == "__main__":
    b = remaining()
    if b["limit"] is None:
        print(f"spent ${b['spent']:.4f}; this key has no limit")
    else:
        print(f"spent ${b['spent']:.4f} of ${b['limit']:.2f}, remaining ${b['remaining']:.4f}")
