import argparse
import csv
import json
import os
import sys
from pathlib import Path

from .config import load_environment
from .pipeline import enrich_qualified, load_candidates, research_candidate
from .providers import ApolloClient, HunterClient, ProviderError, TavilyClient, TinyFishClient
from .web import serve
from .storage import Database


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dasyante", description="Evidence-backed Dasyante lead research")
    commands = parser.add_subparsers(dest="command", required=True)

    research = commands.add_parser("research", help="research candidate companies")
    research.add_argument("--input", required=True, type=Path)
    research.add_argument("--db", default="dasyante.db", type=Path)
    research.add_argument("--dry-run", action="store_true")
    apollo_controls = research.add_mutually_exclusive_group()
    apollo_controls.add_argument("--skip-apollo", action="store_true", help="skip company profiles and Apollo credits")
    apollo_controls.add_argument("--refresh-apollo", action="store_true", help="bypass the seven-day company profile cache")

    discover = commands.add_parser("discover", help="search Apollo organizations")
    discover.add_argument("--query", required=True, help="company name or organization query")
    discover.add_argument("--page", default=1, type=int)
    discover.add_argument("--per-page", default=25, type=int)
    discover.add_argument("--output", type=Path, help="optional JSON output path")

    review = commands.add_parser("review", help="approve candidates for contact enrichment")
    review.add_argument("--db", default="dasyante.db", type=Path)
    review.add_argument("--candidate-id", required=True)

    enrich = commands.add_parser("enrich", help="enrich manually selected decision makers")
    enrich.add_argument("--db", default="dasyante.db", type=Path)
    enrich.add_argument("--candidate-id", required=True)
    enrich.add_argument("--contacts", required=True, type=Path, help="Apollo-exported CSV with first_name,last_name,title and domain or candidate_id")

    export = commands.add_parser("export", help="export stored leads")
    export.add_argument("--db", default="dasyante.db", type=Path)
    export.add_argument("--output", required=True, type=Path)
    export.add_argument("--format", choices=("json", "csv"), default="json")
    web = commands.add_parser("serve", help="open the local research workspace")
    web.add_argument("--db", default="dasyante.db", type=Path)
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", default=8765, type=int)
    return parser

def _research(args: argparse.Namespace) -> int:
    candidates = load_candidates(args.input)
    apollo_key = os.environ.get("APOLLO_API_KEY", "")
    use_apollo = bool(apollo_key) and not args.skip_apollo
    if args.dry_run:
        profile_count = len(candidates) if use_apollo else 0
        print(f"{len(candidates)} candidate(s); {len(candidates) * 4} searches; up to {len(candidates) * 2} triage pages; up to {profile_count} Apollo company profiles (cached profiles use no new credits)")
        return 0
    tavily = TavilyClient(os.environ.get("TAVILY_API_KEY", ""))
    tinyfish = TinyFishClient(os.environ.get("TINYFISH_API_KEY", ""))
    apollo = ApolloClient(apollo_key) if use_apollo else None
    database = Database(args.db)
    try:
        for candidate in candidates:
            score = research_candidate(candidate, tavily.search, tinyfish.scrape, database,
                                       company_enrich=apollo.enrich_company if apollo else None,
                                       refresh_apollo=args.refresh_apollo)
            print(f"{candidate.name}: {score}/100")
            stored = database.get_candidate_by_domain(candidate.domain)
            profile = database.company_profile_for(stored["id"]) if stored else None
            if apollo and profile and profile["status"] == "error":
                print(f'warning: {candidate.name}: Apollo profile unavailable: {profile["error"]}', file=sys.stderr)
        print(json.dumps({"usage": database.usage()}, indent=2))
    finally:
        database.close()
    return 0


def _discover(args: argparse.Namespace) -> int:
    client = ApolloClient(os.environ.get("APOLLO_API_KEY", ""))
    result = client.search_organizations(args.query, args.page, args.per_page)
    serialized = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
        print(f"wrote {len(result['organizations'])} organization(s) to {args.output}")
    else:
        print(serialized)
    return 0


def _review(args: argparse.Namespace) -> int:
    database = Database(args.db)
    try:
        row = database.get_candidate(args.candidate_id)
        if row is None:
            raise ValueError("candidate does not exist")
        if not row["qualified"]:
            raise ValueError("only qualified candidates can be reviewed")
        database.mark_reviewed(args.candidate_id)
        print(f"approved {args.candidate_id} for contact enrichment")
    finally:
        database.close()
    return 0

def _enrich(args: argparse.Namespace) -> int:
    hunter_key = os.environ.get("HUNTER_API_KEY", "")
    hunter = HunterClient(hunter_key) if hunter_key else None
    with args.contacts.open(newline="", encoding="utf-8") as handle:
        contact_rows = list(csv.DictReader(handle))

    def field(row: dict[str, str], *names: str) -> str:
        for name in names:
            value = row.get(name, "").strip()
            if value:
                return value
        return ""

    def finder(domain: str) -> list[dict[str, str]]:
        results = []
        for row in contact_rows:
            row_domain = field(row, "domain", "Domain", "Company Domain", "website", "Website").lower().removeprefix("www.")
            if field(row, "candidate_id", "Candidate ID") != args.candidate_id and row_domain != domain:
                continue
            first_name = field(row, "first_name", "First Name", "First name")
            last_name = field(row, "last_name", "Last Name", "Last name")
            if not first_name or not last_name:
                raise ValueError("contact CSV rows require first_name and last_name")
            email = field(row, "email", "Email", "Email Address")
            status = field(row, "email_status", "Email Status") or "unknown"
            if not email and hunter:
                email = hunter.find_email(domain, first_name, last_name)
                database.increment_usage("hunter_email_finder")
            if email and hunter:
                status = hunter.verify_email(email)
                database.increment_usage("hunter_email_verifier")
            results.append({
                "first_name": first_name,
                "last_name": last_name,
                "title": field(row, "title", "Title"),
                "email": email,
                "email_status": status,
                "linkedin_url": field(row, "linkedin_url", "LinkedIn URL", "Linkedin URL"),
            })
            database.increment_usage("apollo_csv_import")
        if not results:
            raise ValueError("no Apollo-exported contacts matched this candidate")
        return results

    database = Database(args.db)
    try:
        count = enrich_qualified(database, args.candidate_id, finder)
        print(f"imported {count} Apollo contact(s)")
    finally:
        database.close()
    return 0



def _export(args: argparse.Namespace) -> int:
    database = Database(args.db)
    rows = database.export()
    if args.format == "json":
        args.output.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    else:
        with args.output.open("w", newline="", encoding="utf-8") as handle:
            profile_fields = ("industry", "employee_count", "location", "total_funding", "latest_funding_stage", "latest_funding_date", "technologies")
            fields = ("id", "name", "website", "domain", "score", "qualified", "reviewed", "apollo_status", "apollo_fetched_at", "apollo_error", *profile_fields)
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                profile = row.get("company_profile") or {}
                data = profile.get("data") or {}
                values = {key: row[key] for key in fields[:7]}
                values.update({key: data.get(key, "") for key in profile_fields})
                values["apollo_status"] = profile.get("status", "")
                values["apollo_fetched_at"] = profile.get("fetched_at", "")
                values["apollo_error"] = profile.get("error", "")
                values["technologies"] = "; ".join(data.get("technologies", []))
                writer.writerow(values)
    print(f"exported {len(rows)} candidate(s) to {args.output}")
    database.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    commands = {
        "research": _research,
        "discover": _discover,
        "review": _review,
        "enrich": _enrich,
        "export": _export,
        "serve": lambda options: serve(options.db, options.host, options.port) or 0,
    }
    try:
        load_environment()
        return commands[args.command](args)
    except (ProviderError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
