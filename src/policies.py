"""Section-based retrieval over the structured store policies.

The store manual is only 8 pages, so a vector RAG index would add cost and
failure modes without improving retrieval: the policy that answers a question
is almost always one whole section (returns, hours, payments...). This module
parses ``data/policies.md`` into sections and ranks them by keyword overlap
with the query (accent-insensitive). The agent always quotes the section it
retrieved instead of paraphrasing policy from memory.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .data_loader import normalize_text


@dataclass
class PolicySection:
    section_id: str
    title: str
    keywords: list[str]
    text: str


def load_policies(policies_path: str | Path | None = None) -> list[PolicySection]:
    """Parse data/policies.md into sections (## headings, ### sub-sections)."""
    if policies_path is None:
        policies_path = (
            Path(__file__).resolve().parent.parent / "data" / "policies.md"
        )
    text = Path(policies_path).read_text(encoding="utf-8")
    sections: list[PolicySection] = []
    current: PolicySection | None = None
    body_lines: list[str] = []

    def flush() -> None:
        nonlocal current, body_lines
        if current is not None:
            current.text = "\n".join(body_lines).strip()
            sections.append(current)
        body_lines = []

    for line in text.splitlines():
        heading = re.match(r"^(#{2,3})\s+(.+?)\s*$", line)
        if heading:
            flush()
            level, title = heading.group(1), heading.group(2).strip()
            # Numbered headings ("4.1 ...") become stable ids like "4.1".
            number = title.split(" ", 1)[0].rstrip(".")
            section_id = number if re.match(r"^\d+(\.\d+)?$", number) else title
            current = PolicySection(
                section_id=section_id,
                title=title,
                keywords=_keywords(title),
                text="",
            )
            # Keep the heading itself in the body so a section is self-contained.
            body_lines = [line]
        elif current is not None:
            body_lines.append(line)
    flush()
    return sections


def _keywords(title: str) -> list[str]:
    return [word for word in normalize_text(title).split() if len(word) > 2]


# Word variants (verb forms, plurals) mapped to the canonical topic word
# used in TOPIC_SYNONYMS and in the policy text, so plain-Portuguese
# questions ("me arrependi, quero devolver") find the right section.
WORD_VARIANTS = {
    "arrependimento": {"arrependi", "arrependimento", "arrependeu"},
    "devolucao": {"devolver", "devolucao", "devolvendo", "devolvido"},
    "troca": {"troca", "trocar", "trocas"},
    "horario": {"horario", "horarios", "funcionamento", "abre", "fecha"},
    "endereco": {"endereco", "onde", "localizacao"},
    "pagamento": {"pagamento", "pagar", "pix", "parcela", "parcelamento", "boleto", "cartao"},
    "frete": {"frete", "entrega", "envio"},
    "promocao": {"promocao", "promocoes", "desconto", "oferta"},
    "garantia": {"garantia"},
    "defeito": {"defeito", "defeituoso", "quebrado"},
}


def _expand_query_words(words: set[str]) -> set[str]:
    """Add the canonical topic word for every known variant in the query."""
    expanded = set(words)
    for word in words:
        for canonical, variants in WORD_VARIANTS.items():
            if word in variants:
                expanded.add(canonical)
    return expanded
TOPIC_SYNONYMS = {
    "devolucao": ["4", "4.1"],
    "arrependimento": ["4", "4.1"],
    "troca": ["4", "4.2", "4.3", "4.4"],
    "defeito": ["4.2", "8"],
    "garantia": ["8"],
    "horario": ["2"],
    "endereco": ["1", "2"],
    "pagamento": ["3"],
    "pix": ["3", "6"],
    "parcela": ["3"],
    "frete": ["5"],
    "entrega": ["5"],
    "rastreamento": ["5.3"],
    "promocao": ["6"],
    "desconto": ["6"],
    "whatsapp": ["7"],
    "privacidade": ["9"],
    "lgpd": ["9"],
    "acessorio": ["1", "7"],
    "escopo": ["1", "7"],
}


def search_policies(
    topic: str, sections: list[PolicySection] | None = None, top_n: int = 2
) -> list[PolicySection]:
    """Return the most relevant policy sections for a topic (best first)."""
    if sections is None:
        sections = load_policies()
    query_words = _expand_query_words(set(normalize_text(topic).split()))
    if not query_words:
        return []

    def score(section: PolicySection) -> float:
        haystack = normalize_text(section.title + " " + section.text)
        words = set(haystack.split())
        overlap = len(query_words & words)
        # Exact section-number matches from the synonym table win outright.
        bonus = 0.0
        for word in query_words:
            if word in TOPIC_SYNONYMS and section.section_id in TOPIC_SYNONYMS[word]:
                bonus += 3.0
        return overlap + bonus

    ranked = sorted(sections, key=score, reverse=True)
    return [section for section in ranked if score(section) > 0][:top_n]


def get_section(section_id: str, sections: list[PolicySection] | None = None) -> PolicySection | None:
    """Return one section by id (e.g. "4.1"), or None."""
    if sections is None:
        sections = load_policies()
    for section in sections:
        if section.section_id == section_id:
            return section
    return None
