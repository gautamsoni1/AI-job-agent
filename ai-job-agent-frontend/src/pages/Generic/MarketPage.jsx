import { endpoints, listResource } from "../../api/resources";
import { ScoreBar } from "../../components/common/ScoreGauge";
import { CardSkeleton } from "../../components/common/Skeleton";
import { useAsync } from "../../hooks/useAsync";

const MarketPage = () => {
  const { data, loading } = useAsync(() => listResource(endpoints.marketTrends), []);
  const report = data?.data || {};
  if (loading) return <div className="grid gap-4 md:grid-cols-3"><CardSkeleton /><CardSkeleton /><CardSkeleton /></div>;

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold text-slate-950">Market Intel</h2>
        <p className="mt-1 text-sm text-slate-500">{report.market_summary || "Trends are calculated from your recent jobs."}</p>
      </div>
      <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <ScoreBar value={report.user_market_fit_score || 0} label="Market fit score" />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {(report.top_demanded_skills || []).map((skill) => (
          <div key={skill.skill} className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <ScoreBar value={skill.demand_score} label={skill.skill} />
            <p className="mt-2 text-sm text-slate-500">Growth {skill.growth_rate || 0}%</p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default MarketPage;
