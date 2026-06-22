import { useMemo, useState } from "react";
import { interviewApi } from "../../api/interview";
import { pipelineApi } from "../../api/pipeline";
import Badge from "../../components/common/Badge";
import FileDropzone from "../../components/common/FileDropzone";
import { ScoreBar } from "../../components/common/ScoreGauge";
import { useAsync } from "../../hooks/useAsync";
import { usePipelineWebSocket } from "../../hooks/usePipelineWebSocket";
import { showToast } from "../../store/toastStore";
import { downloadBlob } from "../../utils/download";
import { formatRelativeTime } from "../../utils/dates";

const parseTags = (value) => value.split(",").map((item) => item.trim()).filter(Boolean);

const Pipeline = () => {
  const { data: rateLimit, loading } = useAsync(pipelineApi.rateLimit, []);
  const [file, setFile] = useState(null);
  const [form, setForm] = useState({ target_role: "", job_description: "", locations: "", max_jobs: 15 });
  const [run, setRun] = useState(null);
  const [applyResults, setApplyResults] = useState({});
  const [prep, setPrep] = useState(null);
  const [prepLoadingJob, setPrepLoadingJob] = useState(null);
  const [practiceQuestion, setPracticeQuestion] = useState(null);
  const [practiceAnswer, setPracticeAnswer] = useState("");
  const [feedback, setFeedback] = useState(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const { events, result, status } = usePipelineWebSocket(run?.websocket_url, Boolean(run));
  const latest = events.at(-1);

  const jobs = result?.jobs || [];
  const jobsFound = useMemo(() => {
    const event = events.findLast?.((item) => item.stage === "JOB_MATCHED") || events.filter((item) => item.stage === "JOB_MATCHED").at(-1);
    return event?.data || null;
  }, [events]);

  const validateFile = () => {
    if (!file) return "Please choose a resume file.";
    const validType = [".pdf", ".docx"].some((ext) => file.name.toLowerCase().endsWith(ext));
    if (!validType) return "Only PDF and DOCX files are allowed.";
    if (file.size > 10 * 1024 * 1024) return "File must be under 10MB.";
    if (!parseTags(form.target_role).length) return "Add at least one target role.";
    if (parseTags(form.target_role).length > 5) return "Add maximum 5 target roles.";
    return null;
  };

  const submit = async (event) => {
    event.preventDefault();
    const error = validateFile();
    if (error) return showToast(error, "warning");
    const payload = new FormData();
    payload.append("file", file);
    payload.append("target_role", parseTags(form.target_role).join(","));
    payload.append("job_description", form.job_description);
    payload.append("locations", parseTags(form.locations).join(","));
    payload.append("max_jobs", form.max_jobs);
    const started = await pipelineApi.start(payload);
    setRun(started);
    showToast("Pipeline started. Live progress connected.", "success");
  };

  const applyAll = async () => {
    const res = await pipelineApi.applyAll(result.pipeline_id);
    const map = Object.fromEntries((res.results || []).map((item) => [item.job_id, item]));
    setApplyResults(map);
    showToast(`${res.applied_count} applied, ${res.manual_apply_count} manual, ${res.failed_count} failed`, "success");
    if (res.after_apply_sheet_url) await downloadBlob(res.after_apply_sheet_url, "after-apply-jobs.xlsx");
  };

  const applyOne = async (jobId) => {
    const res = await pipelineApi.applyOne(result.pipeline_id, jobId);
    setApplyResults((prev) => ({ ...prev, [jobId]: res }));
    showToast(res.message || "Application updated", res.status === "FAILED" ? "danger" : "success");
  };

  const generatePrep = async (job) => {
    setPrepLoadingJob(job.job_id);
    setFeedback(null);
    setPracticeAnswer("");
    try {
      const kit = await interviewApi.generatePrep(job.job_id);
      setPrep(kit);
      const firstQuestion =
        kit.technical_questions?.[0] ||
        kit.behavioral_questions?.[0] ||
        kit.company_specific_questions?.[0] ||
        null;
      setPracticeQuestion(firstQuestion);
      showToast(`Interview prep generated for ${kit.role} at ${kit.company}`, "success");
    } finally {
      setPrepLoadingJob(null);
    }
  };

  const evaluatePractice = async () => {
    if (!practiceQuestion || !practiceAnswer.trim()) {
      showToast("Choose a question and write your answer first.", "warning");
      return;
    }
    setFeedbackLoading(true);
    try {
      const res = await interviewApi.evaluateAnswer({
        question: practiceQuestion.question,
        answer: practiceAnswer,
        job_context: `${prep.role} at ${prep.company}. Target role: ${result.target_role || result.target_roles?.join(", ") || ""}.`,
      });
      setFeedback(res);
      showToast(`Practice evaluated: ${res.score}/10`, "success");
    } finally {
      setFeedbackLoading(false);
    }
  };

  const questionGroups = prep
    ? [
        ["Technical", prep.technical_questions || []],
        ["Behavioral", prep.behavioral_questions || []],
        ["Company-Specific", prep.company_specific_questions || []],
      ]
    : [];

  if (loading) return <div className="rounded-lg border border-slate-200 bg-white p-6 text-slate-500">Checking pipeline availability...</div>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold text-slate-950">Pipeline</h2>
          <p className="mt-1 text-sm text-slate-500">Upload once, analyze resume, improve ATS, discover jobs, match them, and export results.</p>
        </div>
        <Badge variant={rateLimit?.can_run ? "success" : "warning"}>{rateLimit?.message || status}</Badge>
      </div>

      {!result && (
        <section className="grid gap-6 xl:grid-cols-[1fr_0.85fr]">
          <form className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm" onSubmit={submit}>
            <div className="space-y-4">
              <FileDropzone file={file} onChange={setFile} />
              <input className="w-full rounded-md border border-slate-300 px-3 py-2.5 text-sm" placeholder="Python Developer, Backend Engineer, Django Developer" value={form.target_role} onChange={(e) => setForm({ ...form, target_role: e.target.value })} />
              <textarea className="min-h-32 w-full rounded-md border border-slate-300 px-3 py-2.5 text-sm" placeholder="Optional job description" value={form.job_description} onChange={(e) => setForm({ ...form, job_description: e.target.value })} />
              <input className="w-full rounded-md border border-slate-300 px-3 py-2.5 text-sm" placeholder="Bangalore, Remote" value={form.locations} onChange={(e) => setForm({ ...form, locations: e.target.value })} />
              <label className="block text-sm font-medium text-slate-600">
                Max jobs: {form.max_jobs}
                <input className="mt-2 w-full accent-[#1F4E79]" type="range" min="1" max="40" value={form.max_jobs} onChange={(e) => setForm({ ...form, max_jobs: Number(e.target.value) })} />
              </label>
              <div className="rounded-md border border-blue-100 bg-blue-50 p-3 text-sm text-blue-800">
                This will analyze your resume, boost ATS score, search LinkedIn, Indeed, Naukri and Glassdoor, match jobs, and prepare a spreadsheet. Usually takes 2-5 minutes.
              </div>
              <button className="rounded-md bg-[#1F4E79] px-4 py-2.5 text-sm font-semibold text-white" disabled={!rateLimit?.can_run || Boolean(run)}>
                {run ? "Pipeline running..." : "Start pipeline"}
              </button>
            </div>
          </form>

          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-slate-950">Live progress</h3>
              <Badge variant={status === "error" ? "danger" : status === "done" ? "success" : "info"}>{status}</Badge>
            </div>
            <div className="mt-5">
              <ScoreBar value={latest?.percent || 0} label={latest?.message || "Waiting to start"} />
              {jobsFound && <p className="mt-3 text-sm font-medium text-slate-700">{jobsFound.jobs_found} / {jobsFound.max_jobs} jobs found</p>}
            </div>
            <div className="scrollbar-thin mt-5 max-h-96 space-y-3 overflow-auto rounded-md bg-slate-950 p-4 font-mono text-xs text-slate-100">
              {events.length ? events.map((event, index) => (
                <div key={`${event.stage}-${index}`} className={event.stage === "ERROR" ? "text-red-300" : event.stage === "DONE" ? "text-emerald-300" : ""}>
                  <span className="text-slate-400">{formatRelativeTime(event.timestamp)}</span> [{event.stage}] {event.message}
                </div>
              )) : <div className="text-slate-400">Progress messages will appear here.</div>}
            </div>
          </div>
        </section>
      )}

      {result && (
        <section className="space-y-5">
          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h3 className="text-lg font-semibold text-slate-950">Pipeline complete</h3>
                <p className="text-sm text-slate-500">{result.message}</p>
              </div>
              <div className="flex gap-3">
                {result.optimized_resume_download_url && <button className="rounded-md border border-slate-200 px-4 py-2 text-sm font-semibold" onClick={() => downloadBlob(result.optimized_resume_download_url, "optimized-resume")}>Download Resume</button>}
                {result.before_apply_sheet_url && <button className="rounded-md border border-slate-200 px-4 py-2 text-sm font-semibold" onClick={() => downloadBlob(result.before_apply_sheet_url, "matched-jobs.xlsx")}>Download Spreadsheet</button>}
                <button className="rounded-md bg-[#1F4E79] px-4 py-2 text-sm font-semibold text-white" onClick={applyAll}>Apply to All</button>
              </div>
            </div>
            <div className="mt-5 grid gap-4 md:grid-cols-3">
              <ScoreBar value={result.initial_ats_score} label="Initial ATS" />
              <ScoreBar value={result.final_ats_score} label="Final ATS" />
              <ScoreBar value={Math.max(0, (result.final_ats_score || 0) - (result.initial_ats_score || 0))} label="Improvement" />
            </div>
            {result.ats_quality_warning && (
              <div className="mt-5 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">{result.ats_quality_warning.message}</div>
            )}
          </div>

          <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-200 px-5 py-4">
              <h3 className="font-semibold text-slate-950">{jobs.length} matched jobs</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-left text-sm">
                <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Role</th><th className="px-4 py-3">Company</th><th className="px-4 py-3">Location</th><th className="px-4 py-3">Match</th><th className="px-4 py-3">Source</th><th className="px-4 py-3">Salary</th><th className="px-4 py-3">Apply Link</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {jobs.map((job) => (
                    <tr key={job.job_id}>
                      <td className="px-4 py-3 font-medium text-slate-950">{job.title}</td>
                      <td className="px-4 py-3 text-slate-600">{job.company}</td>
                      <td className="px-4 py-3 text-slate-600">{job.location || "Remote/NA"}</td>
                      <td className="px-4 py-3"><ScoreBar compact value={job.match_score} /></td>
                      <td className="px-4 py-3"><Badge variant="info">{job.source || "Web"}</Badge></td>
                      <td className="px-4 py-3 text-slate-600">{job.salary_range || "Not listed"}</td>
                      <td className="px-4 py-3">
                        {job.apply_link ? (
                          <a className="inline-flex rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-medium text-[#1F4E79]" href={job.apply_link} target="_blank" rel="noreferrer">
                            Open apply link
                          </a>
                        ) : (
                          <span className="text-slate-400">Not provided</span>
                        )}
                      </td>
                      <td className="px-4 py-3"><Badge variant={applyResults[job.job_id]?.status === "FAILED" ? "danger" : applyResults[job.job_id]?.status ? "success" : "neutral"}>{applyResults[job.job_id]?.status || "NOT_APPLIED"}</Badge></td>
                      <td className="space-x-2 px-4 py-3">
                        <button className="rounded-md border border-slate-200 px-3 py-2 text-sm font-medium" onClick={() => applyOne(job.job_id)}>Apply</button>
                        <button className="rounded-md bg-slate-950 px-3 py-2 text-sm font-medium text-white" onClick={() => generatePrep(job)} disabled={prepLoadingJob === job.job_id}>
                          {prepLoadingJob === job.job_id ? "Preparing..." : "Interview Prep"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {prep && (
            <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h3 className="text-lg font-semibold text-slate-950">Interview Preparation</h3>
                  <p className="mt-1 text-sm text-slate-500">
                    {prep.role} at {prep.company}, based on your active resume and this matched job profile.
                  </p>
                </div>
                <Badge variant="info">{prep.company}</Badge>
              </div>

              <div className="mt-5 grid gap-5 xl:grid-cols-[1fr_0.85fr]">
                <div className="space-y-5">
                  {questionGroups.map(([label, questions]) => (
                    <div key={label} className="rounded-md border border-slate-200">
                      <div className="border-b border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-950">{label}</div>
                      <div className="divide-y divide-slate-100">
                        {questions.length ? questions.map((question, index) => (
                          <details key={`${label}-${index}`} className="p-4">
                            <summary className="cursor-pointer text-sm font-medium text-slate-950">{question.question}</summary>
                            <div className="mt-3 rounded-md bg-slate-50 p-3 text-sm text-slate-600">
                              <p className="font-medium text-slate-800">Model answer</p>
                              <p className="mt-1">{question.model_answer}</p>
                              {question.tips?.length ? <ul className="mt-3 list-disc pl-5">{question.tips.map((tip) => <li key={tip}>{tip}</li>)}</ul> : null}
                              <button className="mt-3 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium" onClick={() => { setPracticeQuestion(question); setPracticeAnswer(""); setFeedback(null); }}>
                                Practice this question
                              </button>
                            </div>
                          </details>
                        )) : <p className="p-4 text-sm text-slate-500">No questions generated in this section.</p>}
                      </div>
                    </div>
                  ))}

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-md border border-slate-200 p-4">
                      <p className="text-sm font-semibold text-slate-950">Questions to ask interviewer</p>
                      <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-600">
                        {(prep.questions_to_ask_interviewer || []).map((item) => <li key={item}>{item}</li>)}
                      </ul>
                    </div>
                    <div className="rounded-md border border-slate-200 p-4">
                      <p className="text-sm font-semibold text-slate-950">Preparation checklist</p>
                      <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-600">
                        {(prep.preparation_checklist || []).map((item) => <li key={item}>{item}</li>)}
                      </ul>
                    </div>
                  </div>
                </div>

                <div className="rounded-md border border-slate-200 p-4">
                  <h4 className="font-semibold text-slate-950">Question Practice</h4>
                  <p className="mt-2 text-sm text-slate-600">{practiceQuestion?.question || "Choose a question to practice."}</p>
                  <textarea
                    className="mt-4 min-h-40 w-full rounded-md border border-slate-300 px-3 py-2.5 text-sm"
                    placeholder="Type your answer here. The AI will evaluate it against the job role, company, and your resume context."
                    value={practiceAnswer}
                    onChange={(event) => setPracticeAnswer(event.target.value)}
                  />
                  <button className="mt-3 rounded-md bg-[#1F4E79] px-4 py-2 text-sm font-semibold text-white" onClick={evaluatePractice} disabled={feedbackLoading}>
                    {feedbackLoading ? "Evaluating..." : "Get Feedback"}
                  </button>
                  {feedback && (
                    <div className="mt-4 space-y-4 rounded-md bg-slate-50 p-4 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-950">Score</span>
                        <Badge variant={feedback.score >= 8 ? "success" : feedback.score >= 5 ? "warning" : "danger"}>{feedback.score}/10</Badge>
                      </div>
                      <div>
                        <p className="font-medium text-emerald-700">Strengths</p>
                        <ul className="mt-2 list-disc pl-5 text-slate-600">{feedback.strengths.map((item) => <li key={item}>{item}</li>)}</ul>
                      </div>
                      <div>
                        <p className="font-medium text-amber-700">Improvements</p>
                        <ul className="mt-2 list-disc pl-5 text-slate-600">{feedback.improvements.map((item) => <li key={item}>{item}</li>)}</ul>
                      </div>
                      <div>
                        <p className="font-medium text-slate-950">Stronger answer example</p>
                        <p className="mt-2 text-slate-600">{feedback.better_answer_example}</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
};

export default Pipeline;
