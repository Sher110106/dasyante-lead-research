import csv
import hashlib
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .models import Candidate, Evidence, candidate_from_row
from .providers import ProviderError
from .scoring import qualify, score_signals
from .storage import Database


PUBLIC_RESEARCH_HOSTS = (
    "greenhouse.io",
    "lever.co",
    "myworkdayjobs.com",
    "ashbyhq.com",
    "github.com",
    "news.ycombinator.com",
)


def allowed_research_url(url: str, company_domain: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    return bool(
        parsed.scheme in {"http", "https"}
        and host
        and host != "linkedin.com"
        and not host.endswith(".linkedin.com")
        and (host == company_domain or host.endswith(f".{company_domain}") or any(host.endswith(suffix) for suffix in PUBLIC_RESEARCH_HOSTS))
    )
SIGNAL_TERMS: dict[str, tuple[str, ...]] = {
    "customer_facing_agent": ("customer-facing agent", "customer facing agent", "ai assistant", "copilot", "conversational agent"),
    "persistent_memory": ("persistent memory", "long-term memory", "across sessions", "conversation history"),
    "reliability": ("hallucination", "llm evaluation", "grounding", "evaluation framework", "reliability"),
    "relevant_hiring": ("ai engineer", "ml engineer", "llm engineer", "evaluation engineer", "agent engineer"),
    "multi_model_or_framework": ("langchain", "langgraph", "llamaindex", "multiple models", "multi-model"),
    "recommendations_or_actions": ("recommendations", "takes action", "automates workflows", "decision support"),
    "enterprise_or_regulated": ("enterprise customers", "healthcare", "financial services", "compliance", "regulated"),
    "recent_launch_or_scale": ("launched", "now available", "announced", "scaling", "series a", "series b"),
}


def _candidate_id(candidate: Candidate) -> str:
    return hashlib.sha256(candidate.domain.encode("utf-8")).hexdigest()[:16]


def load_candidates(path: str | Path) -> list[Candidate]:
    seen: set[str] = set()
    candidates: list[Candidate] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            candidate = candidate_from_row(row)
            if candidate.domain in seen:
                continue
            seen.add(candidate.domain)
            candidates.append(Candidate(candidate.name, candidate.website, candidate.linkedin_url, _candidate_id(candidate)))
    return candidates


def _excerpt(text: str, start: int, term: str) -> str:
    left = max(0, start - 100)
    right = min(len(text), start + len(term) + 140)
    return " ".join(text[left:right].split())


def extract_signals(text: str, url: str, source_tier: str = "T1") -> dict[str, list[Evidence]]:
    lowered = text.lower()
    result: dict[str, list[Evidence]] = {}
    for signal, terms in SIGNAL_TERMS.items():
        for term in terms:
            index = lowered.find(term)
            if index >= 0:
                result[signal] = [Evidence("yes", _excerpt(text, index, term), url, source_tier)]
                break
    return result


def enrich_company_profile(
    database: Database,
    candidate_id: str,
    finder: Callable[[str], dict[str, Any] | None],
    refresh: bool = False,
) -> dict[str, Any]:
    row = database.get_candidate(candidate_id)
    if row is None:
        raise ValueError("candidate does not exist")
    cached = database.company_profile_for(candidate_id)
    if not refresh and cached and cached["status"] in {"success", "not_found"}:
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(cached["fetched_at"])
            if timedelta(0) <= age < timedelta(days=7):
                return cached
        except (ValueError, TypeError):
            pass  # Invalid or legacy timestamps must never suppress a real lookup.
    database.increment_usage("apollo_company_enrich")
    try:
        profile = finder(row["domain"])
    except ProviderError as exc:
        database.save_company_profile(candidate_id, None, "error", str(exc))
    else:
        database.save_company_profile(candidate_id, profile, "success" if profile is not None else "not_found")
    return database.company_profile_for(candidate_id)


def research_candidate(
    candidate: Candidate,
    search: Callable[[str], Iterable[object]],
    scrape: Callable[[str], object],
    database: Database,
    *,
    company_enrich: Callable[[str], dict[str, Any] | None] | None = None,
    refresh_apollo: bool = False,
) -> int:
    candidate_id = database.save_candidate(candidate)
    if company_enrich is not None:
        enrich_company_profile(database, candidate_id, company_enrich, refresh=refresh_apollo)
    urls: list[str] = []
    queries = (
        f'"{candidate.name}" AI agent assistant copilot',
        f'"{candidate.name}" AI evaluation hallucination grounding memory',
        f'"{candidate.name}" AI engineer LLM engineer careers',
        f'"{candidate.name}" LangChain LangGraph LlamaIndex models',
    )
    for query in queries:
        database.increment_usage("tavily_search")
        for item in search(query):
            url = getattr(item, "url", "")
            if url and allowed_research_url(url, candidate.domain) and url not in urls:
                urls.append(url)
    for url in urls[:2]:
        database.increment_usage("tinyfish_fetch")
        page = scrape(url)
        extracted = extract_signals(getattr(page, "markdown", ""), url)
        for signal, entries in extracted.items():
            for evidence in entries:
                database.add_evidence(candidate_id, signal, evidence)
    evidence = database.evidence_for(candidate_id)
    score = score_signals(evidence)
    database.set_score(candidate_id, score, qualify(candidate, evidence))
    return score


def enrich_qualified(database: Database, candidate_id: str, finder: Callable[[str], Iterable[dict]]) -> int:
    row = database.get_candidate(candidate_id)
    if row is None:
        raise ValueError("candidate does not exist")
    if not row["qualified"] or not row["reviewed"]:
        raise ValueError("contact enrichment requires a qualified and reviewed candidate")
    contacts = list(finder(row["domain"]))
    for contact in contacts:
        database.add_contact(candidate_id, contact)
    return len(contacts)
