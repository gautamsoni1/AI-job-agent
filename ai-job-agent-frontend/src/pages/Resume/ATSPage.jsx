import { useMemo, useState } from "react";
import { atsApi, resumeApi } from "../../api/resume";
import Badge from "../../components/common/Badge";
import ScoreGauge, { ScoreBar } from "../../components/common/ScoreGauge";
import { useAsync } from "../../hooks/useAsync";
import { showToast } from "../../store/toastStore";
import { downloadBlob } from "../../utils/download";

const List = ({ title, items = [], empty = "No issues found." }) => (
  <div className="rounded-md border border-slate-200 p-4">
    <h4 className="font-medium text-slate-950">{title}</h4>
    {items.length ? <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-600">{items.map((item, index) => <li key={`${item}-${index}`}>{typeof item === "string" ? item : item.action || item.issue || JSON.stringify(item)}</li>)}</ul> : <p className="mt-2 text-sm text-emerald-700">{empty}</p>}
  </div>
);

const ATSPage = () => {
  const resumesState = useAsync(resumeApi.list, []);
  const historyState = useAsync(atsApi.history, []);
  const resumes = useMemo(() => resumesState.data || [], [resumesState.data]);
  const reports = useMemo(() => historyState.data || [], [historyState.data]);
  const [resumeId, setResumeId] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [targetRole, setTargetRole] = useState("");
  const [report, setReport] = useState(null);
  const [working, setWorking] = useState("");
  const [optimized, setOptimized] = useState(null);

  const selectedResumeId = resumeId || (resumes.find((item) => item.is_active) || resumes[0])?.id || "";
  const currentReport = useMemo(() => report || reports.find((item) => item.resume_id === selectedResumeId) || null, [report, reports, selectedResumeId]);

  const check = async () => {
    if (!selectedResumeId) return showToast("Upload a resume first.", "warning");
    setWorking("score");
    try {
      const result = await atsApi.score({ resume_id: selectedResumeId, job_description: jobDescription.trim() || null });
      setReport({ ...result, resume_id: selectedResumeId });
      setOptimized(null);
      await historyState.execute();
      showToast(`ATS check complete: ${Math.round(result.ats_score)}/100`, result.ats_score >= 90 ? "success" : "warning");
    } finally { setWorking(""); }
  };

  const recreate = async () => {
    if (!selectedResumeId) return showToast("Select a resume first.", "warning");
    setWorking("optimize");
    try {
      const result = await resumeApi.optimize(selectedResumeId, { job_description: jobDescription.trim() || null, target_role: targetRole.trim() || null });
      setOptimized(result);
      setResumeId(result.new_resume_id);
      await Promise.all([resumesState.execute(), historyState.execute()]);
      const score = Math.round(result.optimized_sections?.projected_ats_score || 0);
      showToast(`Improved resume created. Verified score: ${score}/100`, score >= 95 ? "success" : "warning");
    } finally { setWorking(""); }
  };

  if (resumesState.loading || historyState.loading) return <div className="rounded-lg border border-slate-200 bg-white p-6 text-slate-500">Loading ATS workspace...</div>;

  return (
    <div className="space-y-6">
      <div><h2 className="text-2xl font-semibold text-slate-950">ATS Scoring</h2><p className="mt-1 text-sm text-slate-500">Check and repair your current resume before starting the job pipeline.</p></div>
      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid gap-4 lg:grid-cols-2">
          <label className="text-sm font-medium text-slate-700">Resume
            <select className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2.5" value={selectedResumeId} onChange={(e) => { setResumeId(e.target.value); setReport(null); setOptimized(null); }}>
              {!resumes.length && <option value="">Upload a resume first</option>}
              {resumes.map((item) => <option key={item.id} value={item.id}>{item.is_active ? "Current · " : ""}{item.label || item.filename} (v{item.version_number})</option>)}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">Target role (recommended for recreation)
            <input className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2.5" value={targetRole} onChange={(e) => setTargetRole(e.target.value)} placeholder="Backend Engineer" />
          </label>
        </div>
        <label className="mt-4 block text-sm font-medium text-slate-700">Job description (optional; gives a job-specific score)
          <textarea className="mt-2 min-h-36 w-full rounded-md border border-slate-300 px-3 py-2.5" value={jobDescription} onChange={(e) => setJobDescription(e.target.value)} placeholder="Paste a job description, or leave blank for a general ATS readiness check." />
        </label>
        <div className="mt-4 flex flex-wrap gap-3">
          <button disabled={!!working || !selectedResumeId} onClick={check} className="rounded-md bg-[#1F4E79] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">{working === "score" ? "Checking..." : "Check current resume"}</button>
          <button disabled={!!working || !selectedResumeId} onClick={recreate} className="rounded-md border border-[#1F4E79] px-4 py-2.5 text-sm font-semibold text-[#1F4E79] disabled:opacity-60">{working === "optimize" ? "Recreating & re-checking..." : "Re-create resume from mistakes"}</button>
        </div>
      </section>

      {currentReport && <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-5"><ScoreGauge value={currentReport.ats_score} label="Current ATS score" /><Badge variant={currentReport.ats_score >= 90 ? "success" : currentReport.ats_score >= 70 ? "warning" : "danger"}>{currentReport.ats_score >= 90 ? "Ready" : "Needs improvement"}</Badge></div>
        <div className="mt-5 grid gap-4 md:grid-cols-3"><ScoreBar value={currentReport.skill_relevance} label="Skill relevance" /><ScoreBar value={currentReport.industry_alignment} label="Industry alignment" /><ScoreBar value={(currentReport.predicted_pass_rate || 0) <= 1 ? (currentReport.predicted_pass_rate || 0) * 100 : currentReport.predicted_pass_rate} label="Predicted pass rate" /></div>
        <div className="mt-5 grid gap-4 lg:grid-cols-2"><List title="Why the score is lower" items={currentReport.formatting_issues || []} /><List title="Missing keywords" items={currentReport.missing_keywords || []} /><List title="How to improve" items={currentReport.improvement_plan || []} /><List title="Section analysis" items={Object.entries(currentReport.section_analysis || {}).map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : value}`)} /></div>
      </section>}

      {optimized && <section className="rounded-lg border border-emerald-200 bg-emerald-50 p-5">
        <h3 className="font-semibold text-emerald-950">Improved resume created and ATS re-checked</h3>
        <p className="mt-2 text-sm text-emerald-800">Verified internal score: {Math.round(optimized.optimized_sections?.original_ats_score || 0)} → {Math.round(optimized.optimized_sections?.projected_ats_score || 0)}/100 ({Math.round(optimized.optimized_sections?.verified_score_improvement || 0)} points better). Content is improved only from available facts; no experience is invented.</p>
        {optimized.optimized_sections?.ats_quality_warning && <p className="mt-2 text-sm text-amber-800">{optimized.optimized_sections.ats_quality_warning.message}</p>}
        <button className="mt-4 rounded-md bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white" onClick={() => downloadBlob(resumeApi.downloadUrl(optimized.new_resume_id), "ats-optimized-resume.docx")}>Download improved resume</button>
      </section>}
    </div>
  );
};

export default ATSPage;
