import { useState } from "react";
import { resumeApi } from "../../api/resume";
import Badge from "../../components/common/Badge";
import FileDropzone from "../../components/common/FileDropzone";
import { useAsync } from "../../hooks/useAsync";
import { showToast } from "../../store/toastStore";
import { downloadBlob } from "../../utils/download";

const ResumesPage = () => {
  const { data: resumes = [], loading, execute: refresh } = useAsync(resumeApi.list, []);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);

  const upload = async () => {
    if (!file) return showToast("Choose a PDF or DOCX resume first.", "warning");
    setUploading(true);
    try {
      const result = await resumeApi.upload(file);
      showToast(`Resume uploaded. Baseline ATS: ${Math.round(result.ats_score || 0)}/100`, "success");
      setFile(null);
      await refresh();
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-slate-950">Resumes</h2>
        <p className="mt-1 text-sm text-slate-500">Upload and manage the resume versions used for ATS checks and pipeline runs.</p>
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="font-semibold text-slate-950">Upload resume before pipeline</h3>
        <div className="mt-4 grid gap-4 md:grid-cols-[1fr_auto] md:items-end">
          <FileDropzone file={file} onChange={setFile} />
          <button disabled={uploading} onClick={upload} className="rounded-md bg-[#1F4E79] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60">
            {uploading ? "Uploading & checking ATS..." : "Upload & check ATS"}
          </button>
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-5 py-4"><h3 className="font-semibold text-slate-950">Uploaded resumes</h3></div>
        {loading ? <p className="p-5 text-sm text-slate-500">Loading resumes...</p> : !resumes.length ? (
          <p className="p-5 text-sm text-slate-500">No resume uploaded yet.</p>
        ) : (
          <div className="divide-y divide-slate-100">
            {resumes.map((resume) => (
              <div key={resume.id} className="flex flex-wrap items-center justify-between gap-4 p-5">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium text-slate-950">{resume.label || resume.filename}</p>
                    {resume.is_active && <Badge variant="success">Current</Badge>}
                    <Badge variant="info">Version {resume.version_number}</Badge>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{resume.filename} · {(resume.file_type || "file").toUpperCase()} · {new Date(resume.created_at).toLocaleString()}</p>
                  {!!resume.skills_extracted?.length && <p className="mt-2 text-sm text-slate-600">Skills: {resume.skills_extracted.slice(0, 10).join(", ")}</p>}
                </div>
                <button onClick={() => downloadBlob(resumeApi.downloadUrl(resume.id), resume.filename)} className="rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700">Download</button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
};

export default ResumesPage;
