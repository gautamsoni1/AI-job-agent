import asyncio
import math
from datetime import datetime
from typing import Callable

import structlog
from apify_client import ApifyClient

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class ApifyService:
    """Fetch jobs from all configured Apify job actors."""

    def __init__(self):
        token = settings.APIFY_TOKEN.strip()
        if not token or token == "apify_api_token":
            logger.warning("apify_token_missing_or_placeholder")
        self.client = ApifyClient(token)

    async def fetch_jobs(
        self,
        keywords: list[str],
        locations: list[str],
        experience_level: str = "mid",
        max_results: int = 100
    ) -> list[dict]:
        """Fetch jobs from LinkedIn, Indeed, Naukri, and Glassdoor."""
        sources = [
            ("LinkedIn",  settings.APIFY_LINKEDIN_ACTOR,  self._linkedin_input,  self._normalize_linkedin),
            ("Indeed",    settings.APIFY_INDEED_ACTOR,    self._indeed_input,    self._normalize_indeed),
            ("Naukri",    settings.APIFY_NAUKRI_ACTOR,    self._naukri_input,    self._normalize_naukri),
            ("Glassdoor", settings.APIFY_GLASSDOOR_ACTOR, self._glassdoor_input, self._normalize_glassdoor),
        ]
        configured_sources = [s for s in sources if s[1]]
        if not configured_sources:
            logger.warning("apify_no_actors_configured")
            return []

        limit = max(10, math.ceil(max_results / len(configured_sources)))
        tasks = [
            self._fetch_source(name, actor_id, input_factory, normalizer,
                               keywords, locations, experience_level, limit)
            for name, actor_id, input_factory, normalizer in configured_sources
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        jobs_by_source = []
        for source, result in zip(configured_sources, results):
            if isinstance(result, Exception):
                logger.error("apify_source_failed", source=source[0], error=str(result))
                continue
            jobs_by_source.append(result)

        jobs = self._dedupe_jobs(self._round_robin(jobs_by_source))[:max_results]
        logger.info("apify_jobs_fetched", count=len(jobs), sources=len(configured_sources))
        return jobs

    async def _fetch_source(
        self,
        source_name: str,
        actor_id: str,
        input_factory: Callable,
        normalizer: Callable[[dict], dict],
        keywords: list[str],
        locations: list[str],
        experience_level: str,
        limit: int,
    ) -> list[dict]:
        try:
            run_input = input_factory(keywords, locations, experience_level, limit)
            result = await self.run_actor(actor_id, run_input)
            jobs = [normalizer(job) for job in result if job]
            jobs = [j for j in jobs if j.get("title") and (j.get("apply_link") or j.get("company"))]
            logger.info("apify_source_jobs_fetched",
                        source=source_name, actor=actor_id, count=len(jobs))
            return jobs
        except Exception as e:
            logger.error("apify_source_fetch_failed",
                         source=source_name, actor=actor_id, error=str(e))
            return []

    # ------------------------------------------------------------------ #
    #  INPUT BUILDERS
    # ------------------------------------------------------------------ #

    def _linkedin_input(self, keywords: list[str], locations: list[str],
                        _: str, limit: int) -> dict:
        """
        curious_coder/linkedin-jobs-scraper — confirmed schema from test.py:
          - urls: required (list of LinkedIn job-search URLs)
          - count: required, must be >= 10
          - scrapeCompany: optional bool
          - proxy: optional

        Extra fields (keyword, location, etc.) are harmless if the actor
        ignores them; they help if a fork uses different field names.
        """
        query    = " ".join(keywords)
        location = locations[0] if locations else "India"
        search_url = self._linkedin_search_url(query, location)
        count = max(10, limit)          # actor validates count >= 10
        return {
            # --- confirmed required fields ---
            "urls":          [search_url],
            "count":         count,
            "scrapeCompany": False,
            # --- common alternate field names across LinkedIn-actor forks ---
            "title":          query,
            "location":       location,
            "searchKeywords": query,
            "keywords":       query,
            "maxItems":       count,
            "maxJobs":        count,
            "proxy":          {"useApifyProxy": True},
        }

    def _indeed_input(self, keywords: list[str], locations: list[str],
                      _: str, limit: int) -> dict:
        return {
            "keyword":  " ".join(keywords),
            "query":    " ".join(keywords),
            "location": locations[0] if locations else "India",
            "maxItems": limit,
            "maxRows":  limit,
            "country":  "in",
        }

    def _naukri_input(self, keywords: list[str], locations: list[str],
                      experience_level: str, limit: int) -> dict:
        return {
            "keyword":  " ".join(keywords),
            "keywords": " ".join(keywords),
            "location": locations[0] if locations else "India",
            "maxItems": limit,
            "maxJobs":  max(50, limit),
            "experience": self._naukri_experience(experience_level),
        }

    def _glassdoor_input(self, keywords: list[str], locations: list[str],
                         _: str, limit: int) -> dict:
        """
        valig/glassdoor-jobs-scraper — commonly accepted fields.
        Multiple field-name variants are sent so the actor picks whichever
        it recognises; extra keys are silently ignored by Apify actors.
        """
        query    = " ".join(keywords)
        location = locations[0] if locations else "India"
        count    = max(10, limit)
        return {
            # Primary fields
            "keyword":      query,
            "query":        query,
            "searchQuery":  query,
            "location":     location,
            # Limit variants
            "maxItems":     count,
            "maxRows":      count,
            "count":        count,
            "limit":        count,
            # Proxy (most Glassdoor actors need it to avoid blocks)
            "proxy":        {"useApifyProxy": True},
        }

    # ------------------------------------------------------------------ #
    #  HELPERS
    # ------------------------------------------------------------------ #

    def _naukri_experience(self, experience_level: str) -> str:
        mapping = {
            "entry": "0", "junior": "1", "mid": "3",
            "senior": "5", "lead": "8", "all": "all",
        }
        value = str(experience_level or "all").strip().lower()
        if value in mapping:
            return mapping[value]
        if value.isdigit() and 0 <= int(value) <= 30:
            return value
        return "all"

    def _linkedin_search_url(self, query: str, location: str) -> str:
        from urllib.parse import urlencode
        params = urlencode({"keywords": query, "location": location})
        return f"https://www.linkedin.com/jobs/search/?{params}"

    async def run_actor(self, actor_id: str, input_data: dict) -> list[dict]:
        """Run an Apify actor and return dataset items."""
        if not actor_id:
            return []
        try:
            run = await asyncio.to_thread(
                self.client.actor(actor_id).call, run_input=input_data
            )
            dataset_id = self._get_default_dataset_id(run)
            if not dataset_id:
                logger.warning("apify_actor_no_dataset", actor=actor_id)
                return []
            return await asyncio.to_thread(self._read_dataset_items, dataset_id)
        except Exception as e:
            logger.error("apify_actor_failed", actor=actor_id, error=str(e))
            return []

    def _read_dataset_items(self, dataset_id: str) -> list[dict]:
        return list(self.client.dataset(dataset_id).iterate_items())

    def _get_default_dataset_id(self, run) -> str:
        if isinstance(run, dict):
            return (run.get("defaultDatasetId")
                    or run.get("default_dataset_id") or "")
        return (getattr(run, "default_dataset_id", "")
                or getattr(run, "defaultDatasetId", "") or "")

    # ------------------------------------------------------------------ #
    #  NORMALIZERS
    # ------------------------------------------------------------------ #

    def _normalize_linkedin(self, raw: dict) -> dict:
        """
        Handles field-name drift across curious_coder actor versions and forks.
        Every commonly-seen variant is tried; first non-empty wins.
        """
        return self._job(
            raw,
            source="LinkedIn",
            title=self._first(raw, "title", "jobTitle", "position",
                              "positionName", "job_title"),
            company=self._first(raw, "companyName", "company", "companyTitle",
                                "company_name", "organization"),
            location=self._first(raw, "location", "jobLocation", "place",
                                 "job_location"),
            description=self._first(raw, "description", "jobDescription",
                                    "descriptionText", "job_description"),
            apply_link=self._first(raw, "applyUrl", "jobUrl", "url", "link",
                                   "job_url", "jobPostingUrl"),
            salary_range=self._first(raw, "salary", "salaryRange",
                                     "salaryInfo", "compensation"),
            experience_required=self._first(raw, "experienceLevel",
                                            "experience", "seniorityLevel",
                                            "seniority_level"),
            employment_type=self._first(raw, "employmentType", "jobType",
                                        "contractType", "employment_type"),
            posted_at=self._first(raw, "postedAt", "listedAt", "postedDate",
                                  "postedTime", "posted_time", "publishedAt"),
            company_logo=self._first(raw, "companyLogo", "logo",
                                     "company_logo_url"),
        )

    def _normalize_indeed(self, raw: dict) -> dict:
        return self._job(
            raw,
            source="Indeed",
            title=self._first(raw, "positionName", "title", "jobTitle"),
            company=self._first(raw, "company", "companyName"),
            location=self._first(raw, "location", "formattedLocation"),
            description=self._first(raw, "description", "jobDescription"),
            apply_link=self._first(raw, "url", "jobUrl", "applyUrl", "link"),
            salary_range=self._first(raw, "salary", "salaryRange"),
            employment_type=self._first(raw, "jobType", "employmentType"),
            posted_at=self._first(raw, "postedAt", "date", "postedDate"),
        )

    def _normalize_naukri(self, raw: dict) -> dict:
        return self._job(
            raw,
            source="Naukri",
            title=self._first(raw, "title", "jobTitle", "designation"),
            company=self._first(raw, "company", "companyName"),
            location=self._first(raw, "location", "jobLocation", "locations"),
            description=self._first(raw, "description", "jobDescription", "jd"),
            apply_link=self._first(raw, "jdURL", "url", "jobUrl",
                                   "applyUrl", "link"),
            salary_range=self._first(raw, "salary", "salaryRange"),
            experience_required=self._first(raw, "experience",
                                            "experienceRequired"),
            employment_type=self._first(raw, "jobType", "employmentType"),
            posted_at=self._first(raw, "postedAt", "postedDate", "createdDate"),
        )

    def _normalize_glassdoor(self, raw: dict) -> dict:
        """
        valig/glassdoor-jobs-scraper field names (and common variants).
        """
        return self._job(
            raw,
            source="Glassdoor",
            title=self._first(raw, "jobTitle", "title", "job_title",
                              "position", "positionName"),
            company=self._first(raw, "employerName", "company", "companyName",
                                "employer", "organization"),
            location=self._first(raw, "location", "jobLocation",
                                 "locationName", "city"),
            description=self._first(raw, "description", "jobDescription",
                                    "fullDescription", "jobListing"),
            apply_link=self._first(raw, "jobViewUrl", "url", "applyUrl",
                                   "jobUrl", "link", "applyLink"),
            salary_range=self._first(raw, "salaryEstimate", "salary",
                                     "salaryRange", "payRange",
                                     "estimatedSalary"),
            experience_required=self._first(raw, "seniorityLevel",
                                            "experience", "experienceLevel",
                                            "seniority"),
            employment_type=self._first(raw, "jobType", "employmentType",
                                        "contractType"),
            posted_at=self._first(raw, "listingAge", "postedAt",
                                  "postedDate", "age", "datePosted"),
            company_logo=self._first(raw, "squareLogo", "companyLogo",
                                     "logo", "employerLogo"),
        )

    # ------------------------------------------------------------------ #
    #  SHARED JOB BUILDER
    # ------------------------------------------------------------------ #

    def _job(self, raw: dict, source: str, **fields) -> dict:
        apply_link = fields.get("apply_link", "") or self._extract_any_url(raw)
        if not apply_link:
            apply_link = self._fallback_search_url(
                source, fields.get("title", ""), fields.get("company", "")
            )
        return {
            "title":               fields.get("title", ""),
            "company":             fields.get("company", ""),
            "location":            fields.get("location", ""),
            "description":         fields.get("description", ""),
            "apply_link":          apply_link,
            "source":              source,
            "salary_range":        fields.get("salary_range", ""),
            "experience_required": fields.get("experience_required", ""),
            "employment_type":     fields.get("employment_type", ""),
            "posted_at":           fields.get("posted_at", ""),
            "company_logo":        fields.get("company_logo", ""),
            "raw_data":            raw,
            "fetched_at":          datetime.utcnow(),
        }

    def _extract_any_url(self, raw: dict) -> str:
        """Scan all string values for a URL-like field when named fields miss."""
        for key, value in raw.items():
            if not isinstance(value, str) or not value.startswith("http"):
                continue
            if any(token in key.lower() for token in ("url", "link", "apply", "jd", "view")):
                return value
        return ""

    def _fallback_search_url(self, source: str, title: str, company: str) -> str:
        """Last-resort search URL so apply_link is never empty."""
        from urllib.parse import quote
        query = quote(f"{title} {company}".strip())
        urls = {
            "LinkedIn":  f"https://www.linkedin.com/jobs/search/?keywords={query}",
            "Indeed":    f"https://in.indeed.com/jobs?q={query}",
            "Naukri":    f"https://www.naukri.com/{quote((title or '').lower().replace(' ', '-'))}-jobs",
            "Glassdoor": f"https://www.glassdoor.co.in/Job/jobs.htm?sc.keyword={query}",
        }
        return urls.get(source, "")

    def _first(self, raw: dict, *keys: str) -> str:
        for key in keys:
            value = raw.get(key)
            if value is None or value == "":
                continue
            if isinstance(value, list):
                return ", ".join(str(item) for item in value if item)
            if isinstance(value, dict):
                for nested_key in ("name", "title", "value", "text"):
                    if value.get(nested_key):
                        return str(value[nested_key])
                return ""
            return str(value)
        return ""

    def _dedupe_jobs(self, jobs: list[dict]) -> list[dict]:
        seen = set()
        unique = []
        for job in jobs:
            key = job.get("apply_link") or "|".join([
                job.get("title", "").lower(),
                job.get("company", "").lower(),
                job.get("location", "").lower(),
            ])
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(job)
        return unique

    def _round_robin(self, job_groups: list[list[dict]]) -> list[dict]:
        merged = []
        max_len = max((len(g) for g in job_groups), default=0)
        for index in range(max_len):
            for group in job_groups:
                if index < len(group):
                    merged.append(group[index])
        return merged