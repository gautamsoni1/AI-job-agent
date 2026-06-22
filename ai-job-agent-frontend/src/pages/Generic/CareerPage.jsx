import { endpoints, listResource } from "../../api/resources";
import Badge from "../../components/common/Badge";
import EmptyState from "../../components/common/EmptyState";
import { CardSkeleton } from "../../components/common/Skeleton";
import { useAsync } from "../../hooks/useAsync";

const CareerPage = () => {
  const { data, loading } = useAsync(() => listResource(endpoints.careerRoadmap), []);
  if (loading) return <div className="grid gap-4 md:grid-cols-3"><CardSkeleton /><CardSkeleton /><CardSkeleton /></div>;

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold text-slate-950">Career Coach</h2>
        <p className="mt-1 text-sm text-slate-500">{data?.summary || "Roadmap, gaps, weekly goals, and career health insights."}</p>
      </div>
      {data ? (
        <>
          <div className="grid gap-4 lg:grid-cols-3">
            {[
              ["Short term", data.short_term_goals],
              ["Mid term", data.mid_term_goals],
              ["Long term", data.long_term_goals],
            ].map(([label, goals]) => (
              <div key={label} className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
                <h3 className="font-semibold text-slate-950">{label}</h3>
                <div className="mt-4 space-y-3">
                  {(goals || []).map((goal, index) => (
                    <div key={index} className="rounded-md border border-slate-200 p-3">
                      <p className="text-sm font-medium text-slate-950">{goal.goal}</p>
                      <p className="mt-1 text-xs text-slate-500">{goal.timeline}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="font-semibold text-slate-950">Recommended skills</h3>
            <div className="mt-3 flex flex-wrap gap-2">{(data.recommended_skills || []).map((skill) => <Badge key={skill} variant="info">{skill}</Badge>)}</div>
          </div>
        </>
      ) : <EmptyState title="No roadmap yet" description="Career coach results will appear after the backend generates them." />}
    </div>
  );
};

export default CareerPage;
