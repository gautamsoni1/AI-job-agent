import api from "./axios";

export const interviewApi = {
  generatePrep: (jobId) => api.post(`/interview/prep/${jobId}`).then((res) => res.data),
  evaluateAnswer: (payload) => api.post("/interview/evaluate", payload).then((res) => res.data),
  history: () => api.get("/interview/history").then((res) => res.data),
};
