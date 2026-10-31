# Empório da Música — Customer-Service Agent

A text customer-service agent for **Empório da Música**, a fictional musical
instruments store in Campo Grande/MS, Brazil. The agent — **Mel** — answers
customers on WhatsApp-style text chat: it searches the catalog, quotes
prices and promotions, looks up orders, applies the store's return policy,
and politely refuses anything outside the store's scope.

Built in Python for the Artefact AI Engineer technical challenge
(Greenhouse job 8111762002). The only mandatory technical constraint —
Python as the main language — is respected; everything else below is a
choice, justified in [Decisions](#decisions).

## How to run

### 1. Requirements

- Python 3.11+
- A Gemini API key (see step 2). The agent makes a handful of API calls per
  conversation; with the default model the cost of the whole evaluation is
  a few cents at most.

### 2. Get a Gemini API key

1. Go to [Google AI Studio](https://aistudio.google.com/apikey) and sign in
   with a Google account.
2. Click **Create API key** and copy it.
3. Note: a Gemini app subscription (e.g. Gemini Pro in the app) is **not**
   the same as API access. The API key is created in AI Studio and is billed
   through the Google Cloud project linked there.

> Never paste your key in a chat, in a terminal command, or in any file that
> is committed. It lives only in your local `.env`.

### 3. Install and configure

```bash
git clone https://github.com/NahLima/emporio-da-musica.git
cd emporio-da-musica
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # then edit .env and add your key
```

`.env`:

```ini
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-2.5-flash   # optional; see "Model" below
```

### 4. Chat with Mel

```bash
python -m src.main
```

Options:

```bash
python -m src.main --today 2026-02-20 --session-id leticia
python -m src.main --message "Quanto custa o Takamine GD20?"
```

- `--today YYYY-MM-DD` sets the reference date used for every deadline
  calculation (default: the system date). It exists so the return example
  is reproducible — see [Example 4](#example-4--the-non-trivial-case).
- `--session-id` persists the conversation history to
  `sessions/<session-id>.json` (gitignored). History is kept in memory
  during a session and reloaded by id, which is what makes follow-ups like
  "e o preço dele?" work: they refer to the previous product.
- Type `sair` to quit.

### 5. Run the tests

```bash
python -m pytest tests/ -q
```

35 tests, no LLM calls, no network. They cover the catalog traps, pricing,
order-total divergences, return eligibility on two reference dates, policy
retrieval and the injection guard.

### 6. Generate the example transcripts

```bash
python scripts/run_examples.py
```

This runs the 5 scenarios through the **real** agent and writes `.md`
transcripts (with the tool calls shown) to `examples/`. It refuses to run
without `GEMINI_API_KEY` — transcripts are never fabricated.

## Example 4 — the non-trivial case

"Me arrependi da minha compra, posso devolver?" is answered by a real
decision chain, not by a canned reply:

1. Mel asks for the order number and the customer's name (privacy: no order
   data is revealed before validation).
2. The customer gives order **7, Letícia Gonçalves Rocha**. The agent calls
   `lookup_order`, which validates the name against the order.
3. The agent calls `check_return` with reason `arrependimento`. The tool
   computes: order delivered, estimated delivery **2026-02-17**, reference
   date **2026-02-20** → 3 days, inside the 7-day withdrawal window.
4. Mel answers: the return is eligible, the ukulele (Shelby SU-21S,
   R$ 159.90, paid in 3x credit) must be in its original packaging with no
   signs of use, the refund goes to the original payment method within up
   to 10 business days, and return shipping is paid by the store.

The conversation is simulated on 2026-02-20 because, on any real date in
late 2026, every order in the data is months past the 7-day window — the
agent would (correctly) refuse. The simulated date is passed explicitly
with `--today 2026-02-20` and recorded in the transcript.

## How it works

```
Customer message (PT-BR)
        │
        ▼
┌──────────────────────────────┐
│  Injection guard (deterministic)  │  injected instructions are data,
│  — never reaches the LLM          │  not instructions
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│  Gemini (gemini-2.5-flash)        │  system prompt: persona Mel + rules
│  generate_content loop            │  temperature 0.3
└──────────────┬───────────────┘
               │ function calls
               ▼
┌──────────────────────────────┐
│  Deterministic tools (src/tools.py)   │
│  search_products · get_product · get_price   │
│  lookup_order · check_return · search_policies │
│  get_store_info                          │
└──────────────┬───────────────┘
               │ structured JSON (prices, stock, deadlines)
               ▼
        Final answer (PT-BR)
```

The LLM decides **which** tool to call and how to phrase the answer. It
never computes a price, a stock level or a deadline: those come from the
tools as structured data.

## Decisions

### Pure function calling, no LangChain / LangGraph

The agent is a single `generate_content` loop in `src/agent.py` (~200
lines). The challenge has ~7 tools, one CLI channel and in-memory history.
A graph framework would add state definitions, nodes and a dependency for
no functional gain, and would make the evaluator's run harder to reproduce.
The loop is isolated in one class, so replacing it with LangGraph later
(see [Next steps](#limitations-and-next-steps)) is a contained change, not a rewrite.

### Gemini via the API, model `gemini-2.5-flash` (pinned)

- The author already has a paid Gemini plan, so this choice needs no new
  account, billing setup or key — the lowest-friction option under a
  3-day deadline.
- Flash is the right tier for this task: the hard work (prices, dates,
  policy text) is done by deterministic tools, so the model only needs
  reliable tool routing and fluent Portuguese, not frontier reasoning.
  A Pro/Sonnet-class model would cost 5–20× more per token without
  changing any answer the customer receives.
- The model is pinned (`gemini-2.5-flash`) and configurable via
  `GEMINI_MODEL` — e.g. `gemini-2.5-pro` can be set without code changes.
- The SDK is `google-genai` (the current SDK; `google-generativeai` is
  deprecated) with the classic `generate_content` API, not the newer
  Interactions API: it is stable, well documented, and the tool loop is
  fully visible in our code instead of hidden server-side.
- Alternatives evaluated: GPT-4o-mini (mature function calling, similar
  cost, but a new OpenAI account + billing) and Claude Sonnet (strongest
  instruction following, but much more expensive and also a new account).
  Both are good models; neither changes the outcome of this challenge
  enough to justify the extra setup.

### Deterministic tools, not LLM arithmetic

Prices, promotions, order totals and return deadlines are computed in
Python (`src/tools.py`) from the CSVs. This is the main defense against
hallucination: the model cannot "remember" a wrong price, because it never
sees one except through a tool result. The same tools are unit-tested
without any LLM call.

### Section-based policy retrieval, not vector RAG

The store manual is 8 pages. It is transcribed into `data/policies.md`
(sections 1–10) and retrieved by keyword overlap with Portuguese word
variants (`src/policies.py`). A vector index would add an embedding model,
a vector store and a reranker to answer questions whose answer is almost
always one whole section. Section retrieval is cheaper, deterministic and
auditable: the agent quotes the section it retrieved. Vector RAG with
reranking is listed under [Next steps](#limitations-and-next-steps) for a larger manual.

### CLI interface

The challenge allows CLI, notebook, API or UI; the focus is the agent
working correctly. A CLI is the smallest interface that exercises the
multi-turn agent and the history, and it runs everywhere with one command.

### Conversation history

History is kept in memory during a session and persisted per `session_id`
as JSON under `sessions/` (gitignored). This is justified by real usage:
customers say "e o preço dele?" referring to the previous product, and
the return flow spans several turns (question → order number → name →
decision). The Gemini API contents are rebuilt per process from the
in-memory turns; the JSON file is the durable record, not the model state.

## Data treatment

The original CSVs and the manual PDF are copied unchanged into `data/`
(verified by checksum). All cleaning happens in code (`src/data_loader.py`):

- Types normalized (`product_id`, `price_brl`, `stock_quantity` as numbers;
  `status` lower-cased; the JSON `specs` column parsed, `{}` on bad input).
- A product is **buyable** only when `status == "active"` AND
  `stock_quantity > 0`.
- Order totals are **recomputed from the items**; the CSV `total_brl` is
  never silently trusted (see below).
- The data-quality problems found are recorded by the loader and surfaced
  by the tools instead of being fixed silently.

### Verified facts the agent must respect

| Fact | Value |
|---|---|
| Products / orders / customers / promotions | 65 / 20 / 50 / 25 |
| Violões (category 5) ≤ R$ 1000 | 14 by price, **12 buyable** |
| Excluded from the 12 | 96 Giannini GF-3D (active, stock 0), 113 Shelby SN-7C (discontinued, stock 0) |
| Takamine GD20 (id 95) | R$ 2,199, stock 5, active, no active promotion; PIX R$ 2,089.05; 12x R$ 183.25 |
| Active promotions (`is_active=1`) | Only 4: product 127 −10%, 121 −20%, 90 −18%, 94 −8% |
| Order 3 total | CSV R$ 3,450 vs items R$ 3,498 (flagged) |
| Order 20 total | CSV R$ 1,400 vs items R$ 1,488 (flagged) |
| Product 130 | `coming_soon`, but sold in orders 3 and 14 (flagged) |
| Categories 6, 7, 8 | Zero products, although the manual claims 300+ instruments |
| Store | Rua 14 de Maio, 3200 — Centro, Campo Grande/MS, CEP 79202-333 |
| Hours | Mon–Fri 09:00–18:00, Sat 09:00–13:00, Sun/holidays closed |
| Returns | Withdrawal 7 days **after receipt**; defect 30 days after purchase; preference 7 days; refund to original payment method within 10 business days; return freight paid by the store |
| Payments | PIX −5%, debit, credit up to 12x interest-free (min. installment R$ 100 for 7–12x, R$ 80 for 4–6x), boleto |
| Shipping (metro Campo Grande) | Free over R$ 500, else R$ 35, 1–3 business days |
| Scope | Instruments only — no accessories (strings, picks, cables, cases, pedals, amplifiers) |

## Assumptions

Where the statement or the data were ambiguous, a reasonable
interpretation was chosen and documented here — not hidden:

1. **Receipt date proxy.** The return rules count 7 days from *receipt*,
   but the CSVs have no receipt date (only `order_date` and
   `estimated_delivery`). `estimated_delivery` is used as the receipt
   proxy, falling back to `order_date`. Every eligibility result states
   which date was used.
2. **Reference date for Example 4.** The Letícia conversation is simulated
   on 2026-02-20. On the real delivery date (late October 2026) no order
   is inside the 7-day window, so a live run would correctly refuse.
3. **Contact data conflict.** The manual lists WhatsApp (67) 3341-4444 on
   the cover and (67) 3321-4500 in section 7, and an e-mail with an accent
   in section 1.2 (invalid). The cover values — (67) 3341-4444 and
   contato@emporiodamusica.com.br — are used, and the conflict is flagged
   in `data/policies.md`.
4. **Order totals.** When the CSV total disagrees with the item sum
   (orders 3 and 20), the item sum is used and the divergence is flagged
   in the tool output and in the answer. No total was "corrected" in the
   data files.
5. **Coming-soon product sold.** Product 130 is `coming_soon` but appears
   in orders 3 and 14. The agent flags this instead of treating the
   product as available.
6. **Catalog size.** The manual claims 300+ instruments; the agent answers
   from the 65-product CSV catalog. Categories with no products are
   reported as such.
7. **Bass name/description mismatches.** Products 135–138 have names that
   disagree with their descriptions (e.g. 135 is named "Music Man" but
   described as a Fender Jazz Bass). The agent presents the catalog name
   and does not invent specifications from the description.
8. **Customer validation.** There is no real authentication in the data
   (no CPF, no password). Validation is order number + full name match.
   This is a prototype-level control, not production authentication.
9. **Preference-exchange window.** The manual says "within 7 days" without
   saying from when; the agent counts from receipt, like the withdrawal
   rule, and says so in the answer.

## Limitations and next steps

- **Automated evaluation.** The 5 example transcripts are manual
  demonstrations. The next step is a scored eval set (golden questions
  with expected tool calls and expected facts in the answer) run in CI,
  so regressions in routing or pricing are caught automatically.
- **RAG with reranking.** If the manual grows (or other documents are
  added), replace section keyword search with embeddings + a reranker,
  keeping the section as the retrieval unit and the citation in the answer.
- **Real customer authentication.** Replace name matching with a real
  login / one-time code before revealing any order data.
- **Guardrails.** Add output validation (e.g. every price in the reply
  must appear in a tool result), a profanity/abuse policy, and a
  human-handoff path that actually creates a ticket instead of only
  offering one.
- **Observability.** Log tool calls, latency, token usage and refusals
  (without personal data) so the store can see which questions the agent
  handles and where it escalates.
- **Deploy.** Wrap the agent in a small HTTP service (FastAPI) behind the
  WhatsApp Business API, with the CLI kept as the local/development
  interface.
- **LangGraph.** With more time, the explicit loop in `src/agent.py`
  could be expressed as a LangGraph graph (tool node, guardrail node,
  human-handoff node). That was deliberately deferred: it adds no
  capability for this scope and would have cost evaluation time.
- **Model fallback.** If Gemini is unavailable, the agent currently fails
  with a clear error. A provider-agnostic LLM interface (same tool
  declarations, different client) would allow a GPT-4o-mini fallback.

## Use of AI coding assistants

This project was built with **Muse (Salem)** as a coding assistant, with
**Naiara Lima** as the author and decision-maker: she defined the stack
(pure function calling, Gemini), the Letícia return case and the reference
date, and approved the architecture. The assistant was used to generate
boilerplate and the first draft of the tools, to review the tool
implementations against the verified data facts, to write the pytest suite,
and to draft the README. Every data fact, price and deadline in the code
was checked against the CSVs and the manual by hand, and the tests encode
those checks. No other candidate's repository was consulted.

## Project structure

```
emporio-da-musica/
├── README.md                 # this file
├── requirements.txt          # google-genai, python-dotenv, pytest
├── .env.example              # GEMINI_API_KEY / GEMINI_MODEL (no real key)
├── data/                     # original CSVs + manual PDF (unchanged)
│   └── policies.md           # structured transcription of the manual
├── src/
│   ├── main.py               # CLI
│   ├── agent.py              # Gemini tool loop + session history
│   ├── tools.py              # deterministic tools (prices, orders, returns)
│   ├── data_loader.py        # CSV loading, normalization, data-quality notes
│   ├── policies.py           # section-based policy retrieval
│   └── prompts.py            # system prompt, persona Mel, refusal replies
├── tests/
│   ├── test_tools.py         # 28 tests: catalog, prices, orders, returns
│   └── test_prompt.py        # 7 tests: prompt rules, injection guard, loop
├── scripts/
│   └── run_examples.py       # generates the 5 example transcripts
├── examples/                 # generated transcripts (see examples/README.md)
└── sessions/                 # per-session JSON history (gitignored)
```

## Troubleshooting

- `GEMINI_API_KEY is not set`: copy `.env.example` to `.env` and add your
  key; the CLI loads `.env` automatically.
- `google-genai` failing to construct its HTTP client with an `InvalidURL`
  error about a port: check for malformed entries in the `NO_PROXY`
  environment variable (e.g. bracketed IPv6 literals that httpx cannot
  parse) and remove them.
- The agent answers in Portuguese by design (the customers speak
  Portuguese). The code, tests, README and example narration are in
  English; only the customer dialogues are in Brazilian Portuguese.
