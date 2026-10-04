from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class Candidate:
    name: str
    website: str
    linkedin_url: str = ""
    candidate_id: str = ""

    @property
    def domain(self) -> str:
        parsed = urlparse(self.website if "://" in self.website else f"https://{self.website}")
        return parsed.netloc.lower().removeprefix("www.")


@dataclass(frozen=True)
class Evidence:
    status: str
    quote: str
    url: str
    source_tier: str = "T1"
    confidence: float = 1.0
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if self.status not in {"yes", "no", "unknown"}:
            raise ValueError("evidence status must be yes, no, or unknown")
        if not 0 <= self.confidence <= 1:
            raise ValueError("evidence confidence must be between 0 and 1")


def normalize_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    return f"https://{host}{path}" if path else f"https://{host}"


def candidate_from_row(row: dict[str, Any]) -> Candidate:
    name = row.get("company_name", row.get("name", "")).strip()
    website = normalize_url(row.get("website", ""))
    if not name or not website:
        raise ValueError("each candidate needs company_name and website")
    return Candidate(name=name, website=website, linkedin_url=row.get("linkedin_url", "").strip())
