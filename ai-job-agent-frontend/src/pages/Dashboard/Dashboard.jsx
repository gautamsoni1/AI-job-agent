import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Link } from "react-router-dom";
import { getDashboard } from "../../api/dashboard";
import Badge from "../../components/common/Badge";
import EmptyState from "../../components/common/EmptyState";
import ScoreGauge, { ScoreBar } from "../../components/common/ScoreGauge";
import { CardSkeleton } from "../../components/common/Skeleton";
import { useAsync } from "../../hooks/useAsync";
import { formatRelativeTime } from "../../utils/dates";

const scoreItems = [
  ["resume_strength_score", "Resume Strength"],
  ["application_success_rate", "Application Success"],
  ["interview_conversion_rate", "Interview Conversion"],
  ["market_readiness_score", "Market Readiness"],
  ["job_search_progress_score", "Search Progress"],
];

const Dashboard = () => {
  const { data, loading } = useAsync(getDashboard, []);
  const scores = data?.scores || {};

  if (loading) {
    return <div className="grid gap-4 md:grid-cols-3"><CardSkeleton /><CardSkeleton /><CardSkeleton /></div>;
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-4 xl:grid-cols-[1.2fr_2fr]">
        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <ScoreGauge value={scores.career_health_score} label="Career Health Score" />
          <div className="mt-6">
            <p className="text-sm font-medium text-slate-600">Weekly goal</p>
            <ScoreBar
              compact
              value={Math.round(((scores.applications_this_week || 0) / (scores.weekly_application_goal || 5)) * 100)}
              label={`${scores.applications_this_week || 0} of ${scores.weekly_application_goal || 5} applications`}
            />
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {scoreItems.map(([key, label]) => (
            <div key={key} className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <ScoreBar value={scores[key]} label={label} />
            </div>
          ))}
          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm font-medium text-slate-600">Top missing skills</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {(scores.top_missing_skills || []).length ? scores.top_missing_skills.map((skill) => <Badge key={skill} variant="warning">{skill}</Badge>) : <span className="text-sm text-slate-500">No gaps found yet.</span>}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-slate-950">ATS Trend</h2>
          {data?.ats_trend?.length ? (
            <div className="mt-4 h-72">
              <ResponsiveContainer>
                <LineChart data={data.ats_trend}>
                  <XAxis dataKey="created_at" hide />
                  <YAxis domain={[0, 100]} />
                  <Tooltip />
                  <Line type="monotone" dataKey="ats_score" stroke="#1F4E79" strokeWidth={2} dot />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : <EmptyState title="No ATS trend yet" description="Upload and score a resume to start tracking improvements." />}
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-950">Top Opportunities</h2>
            <Link className="text-sm font-medium text-[#1F4E79]" to="/jobs">View all</Link>
          </div>
          <div className="mt-4 space-y-3">
            {data?.top_opportunities?.length ? data.top_opportunities.slice(0, 5).map((job) => (
              <div key={job._id} className="flex items-center justify-between rounded-md border border-slate-200 p-3">
                <div>
                  <p className="font-medium text-slate-950">{job.title || "Untitled role"}</p>
                  <p className="text-sm text-slate-500">{job.company || "Unknown company"}</p>
                </div>
                <Badge variant="info">{job.match_score || job.relevance_score || 0}%</Badge>
              </div>
            )) : <EmptyState title="No opportunities yet" description="Run the pipeline to discover matched jobs." action={<Link className="rounded-md bg-[#1F4E79] px-4 py-2 text-sm font-semibold text-white" to="/pipeline">Open pipeline</Link>} />}
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-slate-950">Recent Applications</h2>
          <div className="mt-4 overflow-hidden rounded-md border border-slate-200">
            {data?.recent_applications?.length ? data.recent_applications.slice(0, 5).map((app) => (
              <div key={app._id} className="grid grid-cols-3 gap-3 border-b border-slate-100 p-3 text-sm last:border-b-0">
                <span className="font-medium text-slate-950">{app.title || app.job_title}</span>
                <span className="text-slate-500">{app.company}</span>
                <Badge>{app.status || "TRACKING"}</Badge>
              </div>
            )) : <div className="p-4"><EmptyState title="No applications" description="Applications created by the pipeline will show here." /></div>}
          </div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-slate-950">Recent Activity</h2>
          <div className="mt-4 space-y-4">
            {data?.recent_timeline?.length ? data.recent_timeline.slice(0, 6).map((event) => (
              <div key={event._id} className="border-l-2 border-slate-200 pl-4">
                <p className="text-sm font-medium text-slate-950">{event.title}</p>
                <p className="text-xs text-slate-500">{formatRelativeTime(event.created_at)}</p>
              </div>
            )) : <EmptyState title="No activity yet" description="AI actions and generated assets will appear in your timeline." />}
          </div>
        </div>
      </section>
    </div>
  );
};

export default Dashboard;
