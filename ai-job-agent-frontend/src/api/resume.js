import api from "./axios";

export const resumeApi = {
  list: () => api.get("/resume/").then((res) => res.data),
  upload: (file) => {
    const body = new FormData();
    body.append("file", file);
    return api.post("/resume/upload", body, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then((res) => res.data);
  },
  analyze: (resumeId, targetRole = "") => api
    .post(`/resume/${resumeId}/analyze`, null, { params: { target_role: targetRole } })
    .then((res) => res.data),
  optimize: (resumeId, payload) => api
    .post(`/resume/${resumeId}/optimize`, payload)
    .then((res) => res.data),
  versions: (resumeId) => api.get(`/resume/${resumeId}/versions`).then((res) => res.data),
  downloadUrl: (resumeId) => `/resume/${resumeId}/download`,
};

export const atsApi = {
  history: () => api.get("/ats/history").then((res) => res.data.reports || []),
  score: (payload) => api.post("/ats/score", payload).then((res) => res.data),
};
