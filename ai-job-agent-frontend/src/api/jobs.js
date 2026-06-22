import api from "./axios";

export const jobsApi = {
  list: (params) => api.get("/jobs/", { params }).then((res) => res.data),
  topMatches: (limit = 50) => api.get("/jobs/matches", { params: { limit } }).then((res) => res.data),
  match: (jobId) => api.post(`/jobs/${jobId}/match`).then((res) => res.data),
};
