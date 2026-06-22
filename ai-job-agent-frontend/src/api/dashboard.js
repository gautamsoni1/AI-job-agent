import api from "./axios";

export const getDashboard = () => api.get("/dashboard/").then((res) => res.data);
