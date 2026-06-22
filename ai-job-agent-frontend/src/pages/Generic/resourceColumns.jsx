import Badge from "../../components/common/Badge";
import { ScoreBar } from "../../components/common/ScoreGauge";
import { formatDate } from "../../utils/dates";

const valueFor = (item, keys) =>
  keys.map((key) => item?.[key]).find((value) => value !== undefined && value !== null && value !== "") ||
  "Not available";

export const defaultColumns = [
  { label: "Title", keys: ["title", "name", "role", "headline", "company_name"] },
  { label: "Company", keys: ["company", "company_name"] },
  {
    label: "Status",
    keys: ["status", "event_type"],
    render: (item) => <Badge>{valueFor(item, ["status", "event_type", "source"])}</Badge>,
  },
  { label: "Created", keys: ["created_at"], render: (item) => formatDate(item.created_at || item.updated_at) },
];

export const jobColumns = [
  { label: "Role", keys: ["title", "job_title"] },
  { label: "Company", keys: ["company", "company_name"] },
  { label: "Location", keys: ["location"] },
  {
    label: "Match Ratio",
    keys: ["match_score", "ai_score"],
    render: (item) => {
      const score = Number(item.match_score || item.match_report?.overall_match || item.ai_score || 0);
      return score ? (
        <div className="min-w-36">
          <ScoreBar compact value={Math.round(score)} />
          <span className="text-xs text-slate-500">Resume + role + company fit</span>
        </div>
      ) : (
        <span className="text-xs text-slate-500">Click Match in job detail/API flow</span>
      );
    },
  },
  {
    label: "Apply Link",
    keys: ["apply_link"],
    render: (item) =>
      item.apply_link && item.apply_link !== "Apply link not provided" ? (
        <a
          className="inline-flex rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-medium text-[#1F4E79]"
          href={item.apply_link}
          target="_blank"
          rel="noreferrer"
        >
          Open apply link
        </a>
      ) : (
        <span className="text-slate-400">Not provided</span>
      ),
  },
  { label: "Source", keys: ["source"], render: (item) => <Badge>{valueFor(item, ["source"])}</Badge> },
  {
    label: "Posted",
    keys: ["posted_date"],
    render: (item) => (
      <div>
        <p>{item.posted_date && item.posted_date !== "Posted date not provided" ? formatDate(item.posted_date) : "Posted date not provided"}</p>
        {item.recency_label && <p className="text-xs text-slate-500">{item.recency_label}</p>}
      </div>
    ),
  },
];
