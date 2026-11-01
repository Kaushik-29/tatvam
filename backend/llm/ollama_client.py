"""Minimal Ollama client (local only; nothing leaves the machine)."""

import json
import urllib.request
from typing import Iterator, Optional

from backend import config


class OllamaUnavailable(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, model: Optional[str] = None, url: Optional[str] = None, timeout: Optional[float] = None):
        self.model = model or config.OLLAMA_MODEL
        self.url = (url or config.OLLAMA_URL).rstrip("/")
        self.timeout = timeout or config.OLLAMA_TIMEOUT_S
        if not self.url.startswith(("http://localhost", "http://127.0.0.1", "http://[::1]")):
            # restricted data (e.g. MIMIC) must never be sent to a remote endpoint
            raise ValueError("OLLAMA_URL must point to a local Ollama server")

    def _post(self, path: str, payload: dict, stream: bool = False):
        req = urllib.request.Request(f"{self.url}{path}", data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            return urllib.request.urlopen(req, timeout=self.timeout)
        except Exception as e:
            raise OllamaUnavailable(str(e)) from e

    def available(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=3) as r:
                names = [m["name"] for m in json.load(r).get("models", [])]
            return self.model in names
        except Exception:
            return False

    def generate(self, prompt: str, system: Optional[str] = None, max_tokens: int = 700,
                 temperature: float = 0.1, seed: int = 7) -> str:
        payload = {"model": self.model, "prompt": prompt, "stream": False,
                   "options": {"temperature": temperature, "num_predict": max_tokens, "seed": seed, "num_ctx": 8192}}
        if system:
            payload["system"] = system
        with self._post("/api/generate", payload) as r:
            return json.load(r).get("response", "")

    def stream(self, prompt: str, system: Optional[str] = None, max_tokens: int = 700,
               temperature: float = 0.1, seed: int = 7) -> Iterator[str]:
        payload = {"model": self.model, "prompt": prompt, "stream": True,
                   "options": {"temperature": temperature, "num_predict": max_tokens, "seed": seed, "num_ctx": 8192}}
        if system:
            payload["system"] = system
        with self._post("/api/generate", payload, stream=True) as r:
            for line in r:
                if line.strip():
                    chunk = json.loads(line)
                    if chunk.get("response"):
                        yield chunk["response"]
                    if chunk.get("done"):
                        break
