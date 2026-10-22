"""Transparent SDK auto-wrapper and duck-typed cached response proxy."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Callable
from chronos.models import EventType


class ChronosResponse:
    """A duck-typed response object that supports both dict and attribute access.
    
    Allows cached responses to seamlessly satisfy client code like:
      response.text
      response.choices[0].message.content
      response['key']
    """
    def __init__(self, data: Any):
        self._data = data

    def __getattr__(self, name: str) -> Any:
        if isinstance(self._data, dict):
            if name in self._data:
                val = self._data[name]
                return ChronosResponse(val) if isinstance(val, (dict, list)) else val
            # Common SDK aliases
            if name == "text" and "text" in self._data:
                return self._data["text"]
            if name == "content" and "content" in self._data:
                return self._data["content"]
        raise AttributeError(f"'ChronosResponse' has no attribute '{name}'")

    def __getitem__(self, item: Any) -> Any:
        if isinstance(self._data, (dict, list)):
            val = self._data[item]
            return ChronosResponse(val) if isinstance(val, (dict, list)) else val
        return self._data[item]

    def __repr__(self) -> str:
        return f"ChronosResponse({repr(self._data)})"

    def __str__(self) -> str:
        if isinstance(self._data, dict) and "text" in self._data:
            return str(self._data["text"])
        return str(self._data)

    def unwrap(self) -> Any:
        return self._data


def serialize_sdk_response(response: Any) -> Any:
    """Extract serializable representation from popular LLM SDK response objects."""
    if response is None:
        return None
    if isinstance(response, (str, int, float, bool, dict, list)):
        return response

    # Google GenAI response (.text)
    if hasattr(response, "text"):
        return {"text": response.text}

    # OpenAI ChatCompletion (.choices[0].message.content)
    if hasattr(response, "choices"):
        try:
            first_choice = response.choices[0]
            content = first_choice.message.content if hasattr(first_choice, "message") else str(first_choice)
            return {"choices": [{"message": {"content": content}}], "text": content}
        except Exception:
            pass

    # Generic fallback
    if hasattr(response, "__dict__"):
        try:
            return {k: v for k, v in response.__dict__.items() if not k.startswith("_")}
        except Exception:
            pass

    return str(response)


class ChronosProxy:
    """Dynamic proxy that intercepts LLM client calls and routes them through a Chronos session."""

    INTERCEPTED_METHODS = {
        "generate_content",          # Google GenAI (client.models.generate_content)
        "create",                    # OpenAI / Anthropic (client.chat.completions.create, client.messages.create)
        "generate",                  # LangChain / Custom LLM
        "invoke",                    # LangChain runnable
    }

    def __init__(self, target: Any, session: Any, path: str = ""):
        self._target = target
        self._session = session
        self._path = path

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._target, name)
        new_path = f"{self._path}.{name}" if self._path else name

        # If attribute is callable and in intercepted set, wrap it
        if callable(attr) and name in self.INTERCEPTED_METHODS:
            return self._create_interceptor(attr, name, new_path)

        # If attribute is a sub-object (like client.models or client.chat.completions), proxy it
        if hasattr(attr, "__dict__") or not callable(attr):
            return ChronosProxy(attr, self._session, new_path)

        return attr

    def _create_interceptor(self, method: Callable, method_name: str, full_path: str):
        def intercepted(*args, **kwargs):
            # Determine identifier name (model name or method path)
            model_name = kwargs.get("model") or (args[0] if args and isinstance(args[0], str) else full_path)
            
            inputs = {
                "args": [str(a) if not isinstance(a, (str, int, float, bool, dict, list)) else a for a in args],
                "kwargs": {
                    k: (str(v) if not isinstance(v, (str, int, float, bool, dict, list)) else v)
                    for k, v in kwargs.items()
                }
            }

            def execute():
                raw_res = method(*args, **kwargs)
                return serialize_sdk_response(raw_res)

            # Route through Chronos deterministic step
            result = self._session.step(
                name=str(model_name),
                event_type=EventType.LLM,
                inputs=inputs,
                fn=execute
            )

            # Return a duck-typed response so .text or .choices work out of the box
            return ChronosResponse(result)

        return intercepted
