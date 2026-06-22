import api from "./axios";

export const pipelineApi = {
  rateLimit: () => api.get("/pipeline/rate-limit-status").then((res) => res.data),
  start: (formData) =>
    api
      .post("/pipeline/run/start", formData, { headers: { "Content-Type": "multipart/form-data" } })
      .then((res) => res.data),
  history: () => api.get("/pipeline/history").then((res) => res.data),
  applyAll: (pipelineId) => api.post(`/pipeline/${pipelineId}/apply-all`).then((res) => res.data),
  applyOne: (pipelineId, jobId) =>
    api.post(`/pipeline/${pipelineId}/apply/${jobId}`).then((res) => res.data),
};
