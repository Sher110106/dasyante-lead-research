import json
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen


class ProviderError(RuntimeError):
    pass


class ProviderConfigError(ProviderError):
    pass


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    content: str = ""


@dataclass(frozen=True)
class ScrapeResult:
    url: str
    markdown: str
    title: str = ""




def ensure_public_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower().removeprefix("www.")
    return bool(
        parsed.scheme in {"http", "https"}
        and host
        and host != "linkedin.com"
        and not host.endswith(".linkedin.com")
    )


def _request_data(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    opener: Callable[..., Any] = urlopen,
    timeout: int = 30,
) -> Any:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(url, data=body, method=method, headers=headers or {})
    secrets = [str(value) for key, value in (payload or {}).items() if key.lower() == "api_key"]
    for key, value in (headers or {}).items():
        if key.lower() in {"authorization", "x-api-key", "x-master-key", "x-access-key"}:
            secrets.append(value.removeprefix("Bearer "))
    secrets.extend(parse_qs(urlparse(url).query).get("api_key", []))

    def redact(value: str) -> str:
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED]")
        return value

    try:
        with opener(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ProviderError(f"provider returned HTTP {exc.code}: {redact(detail)[:300]}") from exc
    except URLError as exc:
        raise ProviderError(f"provider request failed: {redact(str(exc.reason))}") from exc
    except TimeoutError as exc:
        raise ProviderError("provider request timed out") from exc
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderError("provider returned invalid JSON") from exc
    return result


def _request_json(*args: Any, **kwargs: Any) -> dict[str, Any]:
    result = _request_data(*args, **kwargs)
    if not isinstance(result, dict):
        raise ProviderError("provider returned an invalid response object")
    return result


class TavilyClient:
    def __init__(self, api_key: str, opener: Callable[..., Any] = urlopen) -> None:
        if not api_key:
            raise ProviderConfigError("TAVILY_API_KEY is required")
        self.api_key = api_key
        self.opener = opener

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        data = _request_json(
            "POST",
            "https://api.tavily.com/search",
            {
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
                "include_answer": False,
                "include_raw_content": False,
            },
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            self.opener,
        )
        return [
            SearchResult(item.get("title", ""), item.get("url", ""), item.get("content", ""))
            for item in data.get("results", [])
            if ensure_public_url(item.get("url", ""))
        ]


class TinyFishClient:
    def __init__(self, api_key: str, opener: Callable[..., Any] = urlopen) -> None:
        if not api_key:
            raise ProviderConfigError("TINYFISH_API_KEY is required")
        self.api_key = api_key
        self.opener = opener

    def scrape(self, url: str) -> ScrapeResult:
        if not ensure_public_url(url):
            raise ProviderError("refusing to scrape a non-public or LinkedIn URL")
        data = _request_json(
            "POST",
            "https://api.fetch.tinyfish.ai",
            {"urls": [url], "format": "markdown", "per_url_timeout_ms": 30_000},
            {
                "X-API-Key": self.api_key,
                "Content-Type": "application/json",
            },
            self.opener,
            timeout=150,
        )
        pages = data.get("results", [])
        if not isinstance(pages, list) or not pages:
            errors = data.get("errors", [])
            code = errors[0].get("error", "unknown") if errors and isinstance(errors[0], dict) else "unknown"
            raise ProviderError(f"TinyFish fetch failed: {code}")
        page = pages[0]
        if not isinstance(page, dict):
            raise ProviderError("TinyFish returned an invalid page")
        markdown = page.get("text")
        if not isinstance(markdown, str) or not markdown.strip():
            raise ProviderError("TinyFish returned empty page content")
        return ScrapeResult(url, markdown, page.get("title") or "")




class ApolloClient:
    def __init__(self, api_key: str, opener: Callable[..., Any] = urlopen) -> None:
        if not api_key:
            raise ProviderConfigError("APOLLO_API_KEY is required")
        self.api_key = api_key
        self.opener = opener

    def enrich_company(self, domain: str) -> dict[str, Any] | None:
        query = urlencode({"domain": domain})
        response = _request_json(
            "GET", f"https://api.apollo.io/api/v1/organizations/enrich?{query}",
            headers={"X-API-Key": self.api_key}, opener=self.opener,
        )
        if "organization" not in response:
            raise ProviderError("Apollo returned an invalid company response")
        organization = response["organization"]
        if organization is None or organization == {}:
            return None
        if not isinstance(organization, dict):
            raise ProviderError("Apollo returned an invalid organization")
        returned_domain = organization.get("primary_domain")
        if not isinstance(returned_domain, str) or returned_domain.lower().removeprefix("www.") != domain:
            raise ProviderError("Apollo returned a mismatched or missing company domain")
        technology_records = organization.get("current_technologies") or organization.get("technology_names") or []
        technologies = []
        if isinstance(technology_records, list):
            for record in technology_records:
                name = record.get("name") if isinstance(record, dict) else record
                if isinstance(name, str) and name and name not in technologies:
                    technologies.append(name)
        location = ", ".join(
            value for field in ("city", "state", "country")
            if isinstance(value := organization.get(field), str) and value
        )
        return {
            "apollo_id": organization.get("id"),
            "name": organization.get("name"),
            "domain": returned_domain,
            "industry": organization.get("industry"),
            "employee_count": organization.get("estimated_num_employees"),
            "location": location,
            "total_funding": organization.get("total_funding_printed") or organization.get("total_funding"),
            "latest_funding_stage": organization.get("latest_funding_stage") or organization.get("latest_funding_round_type"),
            "latest_funding_date": organization.get("latest_funding_round_date"),
            "technologies": technologies,
        }

    def search_organizations(self, query: str, page: int = 1, per_page: int = 25) -> dict[str, Any]:
        """Search Apollo organizations using the trial-compatible endpoint.

        Apollo's newer ``mixed_companies/search`` endpoint is plan-gated for
        Basic (Trial) teams.  The legacy organization search endpoint remains
        available for this account and returns enough context to seed a CSV
        research run.  This method deliberately returns selected fields only.
        """
        query = query.strip()
        if not query:
            raise ValueError("Apollo organization search requires a query")
        if not isinstance(page, int) or page < 1 or not isinstance(per_page, int) or not 1 <= per_page <= 100:
            raise ValueError("Apollo organization search page must be >= 1 and per_page must be 1-100")
        response = _request_json(
            "POST",
            "https://api.apollo.io/api/v1/organizations/search",
            payload={"q_organization_name": query, "page": page, "per_page": per_page},
            headers={"X-API-Key": self.api_key, "Content-Type": "application/json"},
            opener=self.opener,
        )
        organizations = response.get("organizations")
        if not isinstance(organizations, list):
            raise ProviderError("Apollo returned an invalid organization search response")
        selected = []
        for organization in organizations:
            if not isinstance(organization, dict):
                continue
            domain = organization.get("primary_domain")
            if not isinstance(domain, str) or not domain:
                continue
            selected.append({
                "apollo_id": organization.get("id"),
                "name": organization.get("name"),
                "domain": domain.lower().removeprefix("www."),
                "website": organization.get("website_url") or f"https://{domain}",
                "industry": organization.get("industry"),
                "employee_count": organization.get("estimated_num_employees"),
            })
        pagination = response.get("pagination")
        if not isinstance(pagination, dict):
            pagination = {}
        return {"organizations": selected, "pagination": pagination}


class HunterClient:
    def __init__(self, api_key: str, opener: Callable[..., Any] = urlopen) -> None:
        if not api_key:
            raise ProviderConfigError("HUNTER_API_KEY is required")
        self.api_key = api_key
        self.opener = opener

    def find_email(self, domain: str, first_name: str, last_name: str) -> str:
        query = urlencode({"domain": domain, "first_name": first_name, "last_name": last_name, "api_key": self.api_key})
        data = _request_json("GET", f"https://api.hunter.io/v2/email-finder?{query}", opener=self.opener)
        return data.get("data", {}).get("email", "")

    def verify_email(self, email: str) -> str:
        query = urlencode({"email": email, "api_key": self.api_key})
        data = _request_json("GET", f"https://api.hunter.io/v2/email-verifier?{query}", opener=self.opener)
        return data.get("data", {}).get("status", "unknown")
