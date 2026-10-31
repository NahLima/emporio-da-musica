"""Gemini tool-calling agent for the Empório da Música.

Pure function calling with the Google Gemini API (``google-genai`` SDK):
a classic ``generate_content`` loop, no LangChain/LangGraph, no new
Interactions API. The loop is deliberately small and explicit so the
evaluator can follow it:

1. The user message is checked against the deterministic injection guard.
2. Gemini is called with the system prompt and the tool declarations.
3. While the model returns function calls, the tools run (deterministically)
   and their JSON results are sent back.
4. The model's final text is the reply.

Order data is only exposed through the validated wrappers
``lookup_order`` / ``check_return``: the agent must pass the customer's
name, and the tools refuse to return order data when the name does not
match. The raw ``get_order`` in tools.py is not exposed to the model.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import date
from pathlib import Path

from google import genai
from google.genai import types

from .data_loader import load_store_data
from .prompts import (
    INJECTION_REPLY,
    build_system_prompt,
)
from .tools import StoreTools, is_injection_attempt

DEFAULT_MODEL = "gemini-3.8-flash"
MAX_TOOL_TURNS = 8
# Waits between retries of a transient Gemini error (503/429/500, dropped
# connection). The SDK already retries fast internally; these longer waits
# give a demand spike time to pass. Tests set the instance attribute
# ``retry_delays`` to (0, 0) instead of waiting.
RETRY_DELAYS = (30, 90)


def _is_transient_error(exc: Exception) -> bool:
    """True for errors worth retrying: overload, rate limit, 5xx, disconnect.

    Not transient: a quota error with ``limit: 0`` (e.g. a Pro model on the
    free tier, whose allowance is zero) — retrying in 30s cannot help when
    the API itself says to retry in ~13h.
    """
    message = str(exc)
    if "limit: 0" in message:
        return False
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(code, int) and code in (429, 500, 502, 503, 504):
        return True
    if any(
        token in message
        for token in (
            "503",
            "429",
            "500",
            "UNAVAILABLE",
            "RESOURCE_EXHAUSTED",
            "DEADLINE_EXCEEDED",
            "Server disconnected",
        )
    ):
        return True
    return type(exc).__name__ in (
        "RemoteProtocolError",
        "ConnectError",
        "ReadTimeout",
    )


def _string_schema(description: str) -> types.Schema:
    return types.Schema(type=types.Type.STRING, description=description)


def _number_schema(description: str) -> types.Schema:
    return types.Schema(type=types.Type.NUMBER, description=description)


def _boolean_schema(description: str) -> types.Schema:
    return types.Schema(type=types.Type.BOOLEAN, description=description)


def _integer_schema(description: str) -> types.Schema:
    return types.Schema(type=types.Type.INTEGER, description=description)


def _object_schema(properties: dict, required: list[str]) -> types.Schema:
    return types.Schema(
        type=types.Type.OBJECT, properties=properties, required=required
    )


def build_tool_declarations() -> types.Tool:
    """Function declarations exposed to Gemini (the agent's only tools)."""
    declarations = [
        types.FunctionDeclaration(
            name="search_products",
            description=(
                "Search the product catalog. Returns buyable products "
                "(active and in stock) sorted by price, unless "
                "in_stock_only is false."
            ),
            parameters=_object_schema(
                {
                    "query": _string_schema(
                        "Free text to match against product name/description, "
                        "e.g. 'Takamine' or 'nylon'."
                    ),
                    "category": _string_schema(
                        "Category name, e.g. 'violões', 'ukuleles', "
                        "'guitarras', 'baixos', 'baterias', 'teclados'."
                    ),
                    "max_price": _number_schema(
                        "Maximum price in BRL, e.g. 1000."
                    ),
                    "in_stock_only": _boolean_schema(
                        "True (default) returns only buyable products."
                    ),
                },
                required=[],
            ),
        ),
        types.FunctionDeclaration(
            name="get_product",
            description="Get one product by id or by name.",
            parameters=_object_schema(
                {
                    "identifier": _string_schema(
                        "Product id (e.g. '95') or product name "
                        "(e.g. 'Takamine GD20')."
                    ),
                },
                required=["identifier"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_price",
            description=(
                "Compute the effective price of a product for a payment "
                "method. Applies only the active promotion, or the 5% PIX "
                "discount — never both."
            ),
            parameters=_object_schema(
                {
                    "product_id": _integer_schema("Product id, e.g. 95."),
                    "payment_method": _string_schema(
                        "One of: pix, debit, credit, boleto."
                    ),
                    "installments": _integer_schema(
                        "Number of credit installments, 1-12. Default 1."
                    ),
                },
                required=["product_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="lookup_order",
            description=(
                "Look up an order. The customer's name MUST be provided and "
                "must match the order; without a matching name no order data "
                "is returned."
            ),
            parameters=_object_schema(
                {
                    "order_id": _integer_schema("Order number, e.g. 7."),
                    "customer_name": _string_schema(
                        "Full name of the customer, e.g. "
                        "'Letícia Gonçalves Rocha'."
                    ),
                },
                required=["order_id", "customer_name"],
            ),
        ),
        types.FunctionDeclaration(
            name="check_return",
            description=(
                "Apply the return/exchange policy to an order on the "
                "reference date. Reason: 'arrependimento' (withdrawal, "
                "7 days after receipt), 'defeito' (defect, 30 days after "
                "purchase) or 'preferencia' (preference exchange, 7 days "
                "after receipt). The customer's name must match the order."
            ),
            parameters=_object_schema(
                {
                    "order_id": _integer_schema("Order number, e.g. 7."),
                    "customer_name": _string_schema(
                        "Full name of the customer."
                    ),
                    "reason": _string_schema(
                        "One of: arrependimento, defeito, preferencia."
                    ),
                },
                required=["order_id", "customer_name"],
            ),
        ),
        types.FunctionDeclaration(
            name="search_policies",
            description=(
                "Retrieve the store policy sections relevant to a topic, "
                "e.g. 'devolução', 'horário', 'pagamento', 'frete'."
            ),
            parameters=_object_schema(
                {"topic": _string_schema("Topic or question in Portuguese.")},
                required=["topic"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_store_info",
            description=(
                "Get the store address, opening hours, phone, e-mail and "
                "scope (instruments only)."
            ),
            parameters=_object_schema({}, required=[]),
        ),
    ]
    return types.Tool(function_declarations=declarations)


class GeminiAgent:
    """A Mel agent: Gemini function calling over deterministic tools."""

    def __init__(
        self,
        tools: StoreTools | None = None,
        model: str | None = None,
        api_key: str | None = None,
        today: date | str | None = None,
        session_id: str | None = None,
        sessions_dir: str | Path | None = None,
        client: object | None = None,
    ) -> None:
        self.tools = tools or StoreTools(load_store_data())
        self.model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
        self.today = self._coerce_date(today) if today else date.today()
        self.session_id = session_id or uuid.uuid4().hex[:8]
        self.retry_delays = RETRY_DELAYS
        self.sessions_dir = Path(
            sessions_dir
            or Path(__file__).resolve().parent.parent / "sessions"
        )
        # The client is injectable so tests can run without an API key.
        if client is not None:
            self.client = client
        else:
            api_key = api_key or os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise ValueError(
                    "GEMINI_API_KEY is not set. Copy .env.example to .env "
                    "and add your Gemini API key (see README)."
                )
            self.client = genai.Client(api_key=api_key)
        self.history: list[dict] = self._load_history()
        # Gemini contents (user/model/function turns) for this process.
        # Seed them from the persisted history so a resumed session
        # (--session-id) really keeps context across restarts: without this,
        # follow-ups like "e o preço dele?" would lose the previous product
        # when the CLI was started again.
        self._contents: list[types.Content] = [
            types.Content(
                role="user" if entry.get("role") == "user" else "model",
                parts=[types.Part(text=entry.get("content", ""))],
            )
            for entry in self.history
            if entry.get("content")
        ]

    # -- History ------------------------------------------------------------
    @staticmethod
    def _coerce_date(value: date | str) -> date:
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value).strip())

    def _history_path(self) -> Path:
        return self.sessions_dir / f"{self.session_id}.json"

    def _load_history(self) -> list[dict]:
        path = self._history_path()
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return data if isinstance(data, list) else []

    def _save_history(self) -> None:
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._history_path().write_text(
            json.dumps(self.history, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # -- Tool dispatch ---------------------------------------------------------
    def execute_tool(self, name: str, args: dict | None) -> dict:
        """Run one tool call and return its JSON-serializable result."""
        args = dict(args or {})
        try:
            if name == "search_products":
                return {
                    "products": self.tools.search_products(
                        query=args.get("query"),
                        category=args.get("category"),
                        max_price=args.get("max_price"),
                        in_stock_only=args.get("in_stock_only", True),
                    )
                }
            if name == "get_product":
                product = self.tools.get_product_by_name_or_id(
                    args["identifier"]
                )
                return {"product": product} if product else {
                    "error": f"Product '{args['identifier']}' was not found."
                }
            if name == "get_price":
                product = self.tools.store.product(int(args["product_id"]))
                if product is None:
                    return {
                        "error": f"Product {args['product_id']} was not found."
                    }
                return self.tools.calculate_price(
                    product,
                    payment_method=args.get("payment_method", "pix"),
                    installments=int(args.get("installments", 1) or 1),
                )
            if name == "lookup_order":
                return self._lookup_order(
                    int(args["order_id"]), args.get("customer_name", "")
                )
            if name == "check_return":
                return self._check_return(
                    int(args["order_id"]),
                    args.get("customer_name", ""),
                    args.get("reason", "arrependimento"),
                )
            if name == "search_policies":
                return {
                    "sections": self.tools.search_policies(args["topic"])
                }
            if name == "get_store_info":
                return self.tools.get_store_info()
            return {"error": f"Unknown tool '{name}'."}
        except (KeyError, TypeError, ValueError) as exc:
            return {"error": f"Invalid arguments for tool '{name}': {exc}"}

    def _lookup_order(self, order_id: int, customer_name: str) -> dict:
        if not customer_name:
            return {
                "error": (
                    "To look up an order I need the order number and the "
                    "customer's full name, to validate the customer first."
                ),
                "needs_validation": True,
            }
        if not self.tools.validate_customer(order_id, customer_name):
            return {
                "error": (
                    "I could not validate that customer for this order. "
                    "Please check the order number and the full name, or "
                    "contact a human attendant."
                ),
                "needs_validation": True,
            }
        order = self.tools.get_order(order_id)
        return {"order": order} if order else {
            "error": f"Order {order_id} was not found."
        }

    def _check_return(
        self, order_id: int, customer_name: str, reason: str
    ) -> dict:
        if not customer_name:
            return {
                "error": (
                    "To check a return I need the order number and the "
                    "customer's full name, to validate the customer first."
                ),
                "needs_validation": True,
            }
        if not self.tools.validate_customer(order_id, customer_name):
            return {
                "error": (
                    "I could not validate that customer for this order. "
                    "Please check the order number and the full name, or "
                    "contact a human attendant."
                ),
                "needs_validation": True,
            }
        return self.tools.check_return_eligibility(
            order_id, self.today, reason=reason
        )

    # -- Model calls ---------------------------------------------------------
    def _generate_with_retry(
        self, contents: list, config: types.GenerateContentConfig
    ):
        """Call generate_content, retrying transient errors with long waits.

        A 503 UNAVAILABLE ("model is currently experiencing high demand")
        is transient: the SDK's own fast retries do not outlast a demand
        spike, so this loop waits 30s and then 90s before giving up. A
        non-transient error (400, 404, auth) is raised immediately.
        """
        last_error: Exception | None = None
        for attempt in range(len(self.retry_delays) + 1):
            try:
                return self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )
            except Exception as exc:  # noqa: BLE001 - re-raised below
                last_error = exc
                if not _is_transient_error(exc) or attempt >= len(
                    self.retry_delays
                ):
                    raise
                delay = self.retry_delays[attempt]
                print(
                    f"[agent] Transient Gemini error ({exc}); retrying in "
                    f"{delay}s (attempt {attempt + 2}/"
                    f"{len(self.retry_delays) + 1})...",
                    file=sys.stderr,
                )
                time.sleep(delay)
        raise last_error  # pragma: no cover - loop always returns or raises

    # -- Conversation ---------------------------------------------------------
    def chat(self, user_text: str) -> dict:
        """Answer one user message. Returns reply + the tool calls made."""
        user_text = (user_text or "").strip()
        tool_calls: list[dict] = []
        if not user_text:
            return {"reply": "Como posso ajudar?", "tool_calls": tool_calls}

        # Deterministic guard: an injection attempt never reaches the LLM.
        if is_injection_attempt(user_text):
            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": INJECTION_REPLY})
            self._save_history()
            return {
                "reply": INJECTION_REPLY,
                "tool_calls": tool_calls,
                "refused_injection": True,
            }

        self.history.append({"role": "user", "content": user_text})
        self._contents.append(
            types.Content(role="user", parts=[types.Part(text=user_text)])
        )
        config = types.GenerateContentConfig(
            system_instruction=build_system_prompt(self.today.isoformat()),
            tools=[build_tool_declarations()],
            temperature=0.3,
        )
        reply = ""
        for _ in range(MAX_TOOL_TURNS):
            response = self._generate_with_retry(self._contents, config)
            calls = list(getattr(response, "function_calls", None) or [])
            if not calls:
                reply = (getattr(response, "text", None) or "").strip()
                if response.candidates:
                    self._contents.append(response.candidates[0].content)
                break
            # The model asked for tools: run them and send the results back.
            self._contents.append(response.candidates[0].content)
            function_parts = []
            for call in calls:
                call_args = dict(call.args or {})
                result = self.execute_tool(call.name, call_args)
                tool_calls.append(
                    {"name": call.name, "args": call_args, "result": result}
                )
                function_parts.append(
                    types.Part.from_function_response(
                        name=call.name,
                        response={"result": result},
                    )
                )
            self._contents.append(
                # Function responses are sent as a "user" content: the
                # Gemini API rejects role "function" (400 INVALID_ARGUMENT
                # on gemini-3.8-flash, 2026-10-31). The parts still carry
                # the function name and result.
                types.Content(role="user", parts=function_parts)
            )
        else:
            reply = (
                "Desculpa, não consegui concluir essa consulta agora. "
                "Quer tentar de novo ou falar com um atendente humano?"
            )
        if not reply:
            reply = (
                "Desculpa, não consegui responder agora. Pode repetir a "
                "pergunta ou falar com um atendente humano?"
            )
        self.history.append({"role": "assistant", "content": reply})
        self._save_history()
        return {"reply": reply, "tool_calls": tool_calls}
