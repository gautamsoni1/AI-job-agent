from datetime import datetime

import structlog
from apify_client import ApifyClient

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class ApifyService:
    """Fetch jobs from multiple sources via Apify actors."""

    def __init__(self):
        self.client = ApifyClient(settings.APIFY_TOKEN)

    async def fetch_jobs(
        self,
        keywords: list[str],
        locations: list[str],
        experience_level: str = "mid",
        max_results: int = 100
    ) -> list[dict]:
        """Fetch jobs from LinkedIn and Indeed in parallel."""
        all_jobs = []

        linkedin_jobs = await self._fetch_linkedin(keywords, locations, max_results // 2)
        all_jobs.extend(linkedin_jobs)

        indeed_jobs = await self._fetch_indeed(keywords, locations, max_results // 2)
        all_jobs.extend(indeed_jobs)

        logger.info("apify_jobs_fetched", count=len(all_jobs))
        return all_jobs

    async def _fetch_linkedin(self, keywords: list[str], locations: list[str], limit: int) -> list[dict]:
        try:
            run_input = {
                "searchKeywords": " ".join(keywords),
                "location": locations[0] if locations else "India",
                "count": limit,
                "proxy": {"useApifyProxy": True}
            }
            result = await self.run_actor(settings.APIFY_LINKEDIN_ACTOR, run_input)
            return [self._normalize_linkedin(job) for job in result if job]
        except Exception as e:
            logger.error("linkedin_fetch_failed", error=str(e))
            return []

    async def _fetch_indeed(self, keywords: list[str], locations: list[str], limit: int) -> list[dict]:
        try:
            run_input = {
                "keyword": " ".join(keywords),
                "location": locations[0] if locations else "India",
                "maxItems": limit,
                "country": "IN",
            }
            result = await self.run_actor(settings.APIFY_INDEED_ACTOR, run_input)
            return [self._normalize_indeed(job) for job in result if job]
        except Exception as e:
            logger.error("indeed_fetch_failed", error=str(e))
            return []

    async def run_actor(self, actor_id: str, input_data: dict) -> list[dict]:
        """Run an Apify actor and return results."""
        try:
            run = self.client.actor(actor_id).call(run_input=input_data)
            items = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                items.append(item)
            return items
        except Exception as e:
            logger.error("apify_actor_failed", actor=actor_id, error=str(e))
            return []

    def _normalize_linkedin(self, raw: dict) -> dict:
        return {
            "title": raw.get("title", ""),
            "company": raw.get("companyName", ""),
            "location": raw.get("location", ""),
            "description": raw.get("description", ""),
            "apply_link": raw.get("applyUrl") or raw.get("jobUrl", ""),
            "source": "LinkedIn",
            "salary_range": raw.get("salary", ""),
            "experience_required": raw.get("experienceLevel", ""),
            "employment_type": raw.get("employmentType", ""),
            "posted_at": raw.get("postedAt") or raw.get("listedAt", ""),
            "company_logo": raw.get("companyLogo", ""),
            "raw_data": raw,
            "fetched_at": datetime.utcnow(),
        }

    def _normalize_indeed(self, raw: dict) -> dict:
        return {
            "title": raw.get("positionName", ""),
            "company": raw.get("company", ""),
            "location": raw.get("location", ""),
            "description": raw.get("description", ""),
            "apply_link": raw.get("url", ""),
            "source": "Indeed",
            "salary_range": raw.get("salary", ""),
            "experience_required": "",
            "employment_type": raw.get("jobType", ""),
            "posted_at": raw.get("postedAt", ""),
            "company_logo": "",
            "raw_data": raw,
            "fetched_at": datetime.utcnow(),
        }