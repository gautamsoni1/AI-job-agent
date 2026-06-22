import { useState } from "react";
import { interviewApi } from "../../api/interview";
import { jobsApi } from "../../api/jobs";
import Badge from "../../components/common/Badge";
import EmptyState from "../../components/common/EmptyState";
import { ScoreBar } from "../../components/common/ScoreGauge";
import { CardSkeleton } from "../../components/common/Skeleton";
import { useAsync } from "../../hooks/useAsync";
import { showToast } from "../../store/toastStore";
import { formatDate } from "../../utils/dates";

const getScore = (job) => Number(job.match_score || job.match_report?.overall_match || 0);

const MatchingPage = () => {
  const { data, loading, setData } = useAsync(() => jobsApi.topMatches(50), []);
  const [busyJob, setBusyJob] = useState(null);
  const [prep, setPrep] = useState(null);
  const [practiceQuestion, setPracticeQuestion] = useState(null);
  const [practiceAnswer, setPracticeAnswer] = useState("");
  const [feedback, setFeedback] = useState(null);
  const jobs = (data?.jobs || []).filter((job) => getScore(job) >= 80);

  const refreshMatch = async (job) => {
    setBusyJob(job.id);
    try {
      await jobsApi.match(job.id);
      showToast("Match score refreshed", "success");
      const updated = await jobsApi.topMatches(50);
      setData(updated);
    } finally {
      setBusyJob(null);
    }
  };

  const generatePrep = async (job) => {
    setBusyJob(job.id);
    setFeedback(null);
    setPracticeAnswer("");
    try {
      const kit = await interviewApi.generatePrep(job.id);
      setPrep(kit);
      setPracticeQuestion(kit.technical_questions?.[0] || kit.behavioral_questions?.[0] || kit.company_specific_questions?.[0] || null);
      showToast(`Company interview preparation ready for ${kit.company}`, "success");
    } finally {
      setBusyJob(null);
    }
  };

  const evaluate = async () => {
    if (!practiceQuestion || !practiceAnswer.trim()) return showToast("Select a question and type your answer.", "warning");
    const res = await interviewApi.evaluateAnswer({
      question: practiceQuestion.question,
      answer: practiceAnswer,
      job_context: `${prep.role} at ${prep.company}`,
    });
    setFeedback(res);
    showToast(`Answer scored ${res.score}/10`, "success");
  };

  if (loading) return <div className="grid gap-4 md:grid-cols-3"><CardSkeleton /><CardSkeleton /><CardSkeleton /></div>;

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold text-slate-950">Matching</h2>
        <p className="mt-1 text-sm text-slate-500">Jobs with 80%+ resume, company, role, and description fit.</p>
      </div>

      {jobs.length ? (
        <div className="grid gap-4">
          {jobs.map((job) => (
            <div key={job.id} className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <div className="grid gap-5 lg:grid-cols-[1fr_18rem]">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-lg font-semibold text-slate-950">{job.title}</h3>
                    <Badge variant="success">{Math.round(getScore(job))}% match</Badge>
                    <Badge>{job.source}</Badge>
                  </div>
                  <p className="mt-1 text-sm text-slate-600">{job.company} • {job.location}</p>
                  <p className="mt-3 line-clamp-3 text-sm text-slate-500">{job.description}</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {(job.required_skills || []).slice(0, 8).map((skill) => <Badge key={skill} variant="info">{skill}</Badge>)}
                  </div>
                  <p className="mt-3 text-xs text-slate-500">
                    Posted: {job.posted_date && job.posted_date !== "Posted date not provided" ? formatDate(job.posted_date) : "Posted date not provided"}
                  </p>
                </div>
                <div className="space-y-4">
                  <ScoreBar value={Math.round(getScore(job))} label="Match ratio" />
                  <div className="flex flex-wrap gap-2">
                    {job.apply_link && job.apply_link !== "Apply link not provided" && (
                      <a className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-medium text-[#1F4E79]" href={job.apply_link} target="_blank" rel="noreferrer">Open apply link</a>
                    )}
                    <button className="rounded-md border border-slate-200 px-3 py-2 text-sm font-medium" onClick={() => refreshMatch(job)} disabled={busyJob === job.id}>
                      Re-match
                    </button>
                    <button className="rounded-md bg-[#1F4E79] px-3 py-2 text-sm font-semibold text-white" onClick={() => generatePrep(job)} disabled={busyJob === job.id}>
                      Interview Preparation
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState title="No 80%+ matches yet" description="Run matching from jobs or the pipeline. High-fit jobs will appear here once their match score is 80 or above." />
      )}

      {prep && (
        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-lg font-semibold text-slate-950">Preparation for {prep.role} at {prep.company}</h3>
          <div className="mt-5 grid gap-5 xl:grid-cols-[1fr_0.8fr]">
            <div className="space-y-4">
              {[
                ["Technical", prep.technical_questions || []],
                ["Behavioral", prep.behavioral_questions || []],
                ["Company", prep.company_specific_questions || []],
              ].map(([label, questions]) => (
                <div key={label} className="rounded-md border border-slate-200">
                  <div className="border-b border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold">{label}</div>
                  {questions.map((question, index) => (
                    <details key={`${label}-${index}`} className="border-b border-slate-100 p-4 last:border-b-0">
                      <summary className="cursor-pointer text-sm font-medium text-slate-950">{question.question}</summary>
                      <p className="mt-3 text-sm text-slate-600">{question.model_answer}</p>
                      <button className="mt-3 rounded-md border border-slate-200 px-3 py-2 text-sm" onClick={() => { setPracticeQuestion(question); setPracticeAnswer(""); setFeedback(null); }}>Practice</button>
                    </details>
                  ))}
                </div>
              ))}
            </div>
            <div className="rounded-md border border-slate-200 p-4">
              <h4 className="font-semibold text-slate-950">Question Practice</h4>
              <p className="mt-2 text-sm text-slate-600">{practiceQuestion?.question || "Choose a question."}</p>
              <textarea className="mt-4 min-h-40 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" value={practiceAnswer} onChange={(e) => setPracticeAnswer(e.target.value)} placeholder="Write your answer here" />
              <button className="mt-3 rounded-md bg-[#1F4E79] px-4 py-2 text-sm font-semibold text-white" onClick={evaluate}>Get Feedback</button>
              {feedback && (
                <div className="mt-4 rounded-md bg-slate-50 p-4 text-sm text-slate-600">
                  <Badge variant={feedback.score >= 8 ? "success" : "warning"}>{feedback.score}/10</Badge>
                  <p className="mt-3 font-medium text-slate-950">Better answer example</p>
                  <p className="mt-1">{feedback.better_answer_example}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MatchingPage;
