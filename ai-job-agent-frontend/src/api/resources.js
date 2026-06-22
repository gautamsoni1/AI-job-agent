import api from "./axios";

export const endpoints = {
  resumes: "/resume/",
  ats: "/ats/history",
  jobs: "/jobs/",
  matching: "/matching/history",
  applications: "/applications/",
  coverLetters: "/cover-letter/",
  interviewHistory: "/interview/history",
  careerRoadmap: "/career/roadmap",
  marketTrends: "/market/trends",
  timeline: "/timeline/",
  profile: "/profile/",
  adminStats: "/admin/stats",
};

export const listResource = (endpoint, params) =>
  api.get(endpoint, { params }).then((res) => res.data);

export const mutateResource = (method, endpoint, payload) =>
  api({ method, url: endpoint, data: payload }).then((res) => res.data);
