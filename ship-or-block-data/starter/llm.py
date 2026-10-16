"""Calling models through OpenRouter, with retries, parallelism and cost tracking.

    from llm import chat, run_parallel, total_cost
    reply = chat("Say hi", model="google/gemini-2.5-flash-lite")
    reply.text, reply.cost
    replies = run_parallel(lambda case: chat(make_prompt(case), model=...), cases, workers=8)

Set your key once:  export OPENROUTER_API_KEY=sk-or-...
Every call is appended to calls.jsonl (model, tokens, cost) so you can see where the money went.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

URL = "https://openrouter.ai/api/v1/chat/completions"
LOG = "calls.jsonl"
_lock = threading.Lock()
_total = 0.0


@dataclass
class Reply:
    text: str
    model: str
    cost: float
    prompt_tokens: int
    completion_tokens: int


def _cost(usage):
    """Dollar cost of one call. Calls billed through a provider's own key (BYOK)
    report cost 0 and the real price under cost_details; count that too."""
    if usage.get("is_byok"):
        return float((usage.get("cost_details") or {}).get("upstream_inference_cost") or 0.0)
    return float(usage.get("cost") or 0.0)


def total_cost():
    """Dollars spent by this process so far (as reported by OpenRouter)."""
    return _total


def chat(prompt, model, system=None, max_tokens=1000, temperature=0.0, json_mode=False, retries=4):
    """Send one request. prompt is a string or a full messages list. Returns a Reply."""
    global _total
    if model.endswith(":free"):
        raise ValueError(":free models are not allowed in this challenge")
    messages = prompt if isinstance(prompt, list) else [{"role": "user", "content": prompt}]
    if system:
        messages = [{"role": "system", "content": system}] + messages
    body = {"model": model, "messages": messages, "max_tokens": max_tokens,
            "temperature": temperature, "usage": {"include": True}}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    data = json.dumps(body).encode()
    headers = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json"}
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(URL, data=data, headers=headers), timeout=120) as r:
                out = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            if e.code == 402:
                raise RuntimeError("Out of credit: your key's limit is used up.") from e
            if attempt == retries or e.code not in (408, 429, 500, 502, 503, 504):
                raise RuntimeError(f"HTTP {e.code}: {e.read()[:300]!r}") from e
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries:
                raise
        time.sleep(2 ** attempt)
    usage = out.get("usage", {})
    reply = Reply(text=out["choices"][0]["message"]["content"] or "", model=out.get("model", model),
                  cost=_cost(usage), prompt_tokens=usage.get("prompt_tokens", 0),
                  completion_tokens=usage.get("completion_tokens", 0))
    with _lock:
        _total += reply.cost
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.time(), "model": reply.model, "prompt_tokens": reply.prompt_tokens,
                                "completion_tokens": reply.completion_tokens, "cost": reply.cost}) + "\n")
    return reply


def run_parallel(fn, items, workers=8, progress=True):
    """Apply fn to every item with a thread pool. Returns results in input order;
    an item whose call raised gets the exception object instead of a result."""
    results = [None] * len(items)
    done = 0

    def wrap(i):
        nonlocal done
        try:
            results[i] = fn(items[i])
        except Exception as e:  # keep going; the caller decides what to do with failures
            results[i] = e
        with _lock:
            done += 1
            if progress and (done % 25 == 0 or done == len(items)):
                print(f"  {done}/{len(items)} done, ${_total:.4f} spent", flush=True)

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(wrap, range(len(items))))
    return results
