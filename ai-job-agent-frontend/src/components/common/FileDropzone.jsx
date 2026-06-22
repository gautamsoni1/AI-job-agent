const FileDropzone = ({ file, onChange, accept = ".pdf,.docx" }) => (
  <label className="flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-center hover:border-[#1F4E79] hover:bg-blue-50">
    <input
      type="file"
      className="sr-only"
      accept={accept}
      onChange={(event) => onChange(event.target.files?.[0] || null)}
    />
    <span className="text-sm font-semibold text-slate-950">{file ? file.name : "Drop resume here or browse"}</span>
    <span className="mt-1 text-xs text-slate-500">PDF or DOCX, maximum 10MB</span>
  </label>
);

export default FileDropzone;
