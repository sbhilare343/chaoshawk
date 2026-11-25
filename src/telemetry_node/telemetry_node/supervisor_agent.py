"""LLM supervisory boundary with deterministic fallback and safety gates."""
import json
import os
import time
from urllib.request import Request, urlopen

from .supervisor import Observation, Decision, rule_based_decision, validate_recommendation


SYSTEM_PROMPT = """You supervise a simulated UAV. Return only JSON with strategy and timestamp_s.
Allowed strategies: hold, reduce_speed, return_to_home. Never issue motor commands.
Choose conservative actions from the supplied observation; safety gates are authoritative."""


class SupervisoryAgent:
    """Fail over OpenAI -> Gemini -> deterministic safety policy."""
    def __init__(self, endpoint=None, api_key=None, model="gpt-4o-mini",
                 gemini_api_key=None, gemini_model="gemini-2.0-flash", timeout_s=8):
        self.endpoint = endpoint or os.getenv(
            "LLM_API_URL", "https://api.openai.com/v1/chat/completions"
        )
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.model = model
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.gemini_model = os.getenv("GEMINI_MODEL", gemini_model)
        self.timeout_s = timeout_s
        self.last_provider = "deterministic_fallback"

    def _remote_proposal(self, observation):
        payload = {"model": self.model, "temperature": 0,
                   "response_format": {"type": "json_object"},
                   "tools": [{"type": "function", "function": self.tool_schema()}],
                   "tool_choice": {"type": "function", "function": {"name": "set_supervisory_strategy"}},
                   "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                                 {"role": "user", "content": json.dumps(observation.__dict__)}]}
        request = Request(self.endpoint, data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json",
                                   "Authorization": f"Bearer {self.api_key}"})
        with urlopen(request, timeout=self.timeout_s) as response:
            body = json.loads(response.read().decode())
        message = body["choices"][0]["message"]
        if message.get("tool_calls"):
            arguments = message["tool_calls"][0]["function"]["arguments"]
            return json.loads(arguments)
        return json.loads(message["content"])

    def _gemini_proposal(self, observation):
        """Call Gemini's generateContent endpoint using a function declaration."""
        endpoint = os.getenv(
            "GEMINI_API_URL",
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.gemini_model}:generateContent",
        )
        declaration = self.tool_schema()
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [
                {"text": json.dumps(observation.__dict__)}]}],
            "tools": [{"functionDeclarations": [declaration]}],
            "toolConfig": {"functionCallingConfig": {
                "mode": "ANY", "allowedFunctionNames": [declaration["name"]]}},
        }
        request = Request(f"{endpoint}?key={self.gemini_api_key}",
                          data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=self.timeout_s) as response:
            body = json.loads(response.read().decode())
        parts = body["candidates"][0]["content"]["parts"]
        for part in parts:
            if "functionCall" in part:
                return part["functionCall"]["args"]
        for part in parts:
            if "text" in part:
                return json.loads(part["text"])
        raise ValueError("Gemini returned no function call or JSON text")

    def decide(self, observation, now=None):
        now = time.time() if now is None else now
        if self.endpoint and self.api_key:
            try:
                proposal = self._remote_proposal(observation)
                decision = validate_recommendation(proposal, observation, now=now)
                if decision.accepted:
                    self.last_provider = "openai"
                    return decision
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                pass
        if self.gemini_api_key:
            try:
                proposal = self._gemini_proposal(observation)
                decision = validate_recommendation(proposal, observation, now=now)
                if decision.accepted:
                    self.last_provider = "gemini"
                    return decision
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                pass
        self.last_provider = "deterministic_fallback"
        return rule_based_decision(observation, now=now)

    def tool_schema(self):
        return {"name": "set_supervisory_strategy", "description": "Select a bounded UAV strategy",
                "parameters": {"type": "object", "required": ["strategy", "timestamp_s"],
                               "properties": {"strategy": {"enum": ["hold", "reduce_speed", "return_to_home"]},
                                              "timestamp_s": {"type": "number"}}}}
