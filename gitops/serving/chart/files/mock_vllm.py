"""Faux serveur vLLM pour kind (sans GPU) : API OpenAI minimale + métriques au format vLLM.

Sert à valider toute la chaîne (Gateway, EPP, LiteLLM, Prometheus, KEDA, alertes) sans T4.
Latence simulée : 150 ms de prefill + 15 ms par token ; concurrence max 4 (le reste attend).
"""
import argparse, json, os, ssl, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ap = argparse.ArgumentParser()
ap.add_argument("--model", default="mock")
ap.add_argument("--port", type=int, default=8000)
ARGS, _ = ap.parse_known_args()

LOCK = threading.Lock()
SLOTS = threading.Semaphore(4)
S = {"running": 0, "waiting": 0, "success": 0, "prompt": 0, "gen": 0, "queries": 0, "hits": 0}
BUCKETS = [0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
HIST = {n: {"b": [0] * len(BUCKETS), "n": 0, "s": 0.0} for n in
        ("time_to_first_token_seconds", "inter_token_latency_seconds", "e2e_request_latency_seconds",
         "request_queue_time_seconds", "request_prefill_time_seconds", "request_decode_time_seconds")}

def observe(name, v):
    h = HIST[name]
    with LOCK:
        h["n"] += 1
        h["s"] += v
        for i, b in enumerate(BUCKETS):
            if v <= b:
                h["b"][i] += 1

def metrics():
    m = ARGS.model
    L = f'model_name="{m}",engine="0"'
    out = []
    def g(n, v, t="gauge"):
        out.append(f"# TYPE vllm:{n} {t}\nvllm:{n}{{{L}}} {v}")
    with LOCK:
        g("num_requests_running", S["running"])
        g("num_requests_waiting", S["waiting"])
        g("kv_cache_usage_perc", min(1.0, S["running"] / 8))
        g("num_preemptions", 0, "counter")
        out.append(f'# TYPE vllm:request_success counter\nvllm:request_success_total{{{L},finished_reason="stop"}} {S["success"]}')
        out.append(f'# TYPE vllm:prompt_tokens counter\nvllm:prompt_tokens_total{{{L}}} {S["prompt"]}')
        out.append(f'# TYPE vllm:generation_tokens counter\nvllm:generation_tokens_total{{{L}}} {S["gen"]}')
        out.append(f'# TYPE vllm:prefix_cache_queries counter\nvllm:prefix_cache_queries_total{{{L}}} {S["queries"]}')
        out.append(f'# TYPE vllm:prefix_cache_hits counter\nvllm:prefix_cache_hits_total{{{L}}} {S["hits"]}')
        for n, h in HIST.items():
            out.append(f"# TYPE vllm:{n} histogram")
            for b, c in zip(BUCKETS, h["b"]):
                out.append(f'vllm:{n}_bucket{{{L},le="{b}"}} {c}')
            out.append(f'vllm:{n}_bucket{{{L},le="+Inf"}} {h["n"]}')
            out.append(f'vllm:{n}_sum{{{L}}} {h["s"]}')
            out.append(f'vllm:{n}_count{{{L}}} {h["n"]}')
    return "\n".join(out) + "\n"

class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a):
        pass
    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def do_GET(self):
        if self.path.startswith("/metrics"):
            return self._send(200, metrics(), "text/plain; version=0.0.4")
        if self.path.startswith("/health") or self.path == "/ping":
            return self._send(200, "{}")
        if self.path.endswith("/models"):
            return self._send(200, json.dumps({"object": "list", "data": [{"id": ARGS.model, "object": "model"}]}))
        self._send(404, "{}")
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(n) or b"{}")
        t0 = time.time()
        with LOCK:
            S["waiting"] += 1
        SLOTS.acquire()
        q = time.time() - t0
        with LOCK:
            S["waiting"] -= 1
            S["running"] += 1
        try:
            toks = int(req.get("max_tokens") or 16)
            toks = min(toks, 64)
            pt = sum(len(str(x.get("content", "")).split()) for x in req.get("messages", [])) or 8
            time.sleep(0.15)
            ttft = time.time() - t0
            time.sleep(0.015 * toks)
            e2e = time.time() - t0
            text = " ".join(["réponse"] * toks)
            with LOCK:
                S["success"] += 1; S["prompt"] += pt; S["gen"] += toks
                S["queries"] += pt; S["hits"] += pt // 2
            for k, v in (("time_to_first_token_seconds", ttft), ("inter_token_latency_seconds", 0.015),
                         ("e2e_request_latency_seconds", e2e), ("request_queue_time_seconds", q),
                         ("request_prefill_time_seconds", 0.15), ("request_decode_time_seconds", e2e - ttft)):
                observe(k, v)
            body = {"id": "mock", "object": "chat.completion", "model": ARGS.model,
                    "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": text}}],
                    "usage": {"prompt_tokens": pt, "completion_tokens": toks, "total_tokens": pt + toks}}
            self._send(200, json.dumps(body))
        finally:
            with LOCK:
                S["running"] -= 1
            SLOTS.release()

if __name__ == "__main__":
    srv = ThreadingHTTPServer(("0.0.0.0", ARGS.port), H)
    crt, key = "/var/run/kserve/tls/tls.crt", "/var/run/kserve/tls/tls.key"
    if os.environ.get("MOCK_TLS") == "1" and os.path.exists(crt):  # le certificat est monté même si le TLS interne est inactif
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(crt, key)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    srv.serve_forever()
