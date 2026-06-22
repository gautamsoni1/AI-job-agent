import { Navigate, Route, Routes } from "react-router-dom";
import { endpoints } from "../api/resources";
import AppShell from "../components/layout/AppShell";
import ProtectedRoute from "../components/layout/ProtectedRoute";
import Login from "../pages/Auth/Login";
import Register from "../pages/Auth/Register";
import ForgotPassword from "../pages/Auth/ForgotPassword";
import ResetPassword from "../pages/Auth/ResetPassword";
import VerifyEmail from "../pages/Auth/VerifyEmail";
import Dashboard from "../pages/Dashboard/Dashboard";
import Pipeline from "../pages/Pipeline/Pipeline";
import ResourcePage from "../pages/Generic/ResourcePage";
import { defaultColumns, jobColumns } from "../pages/Generic/resourceColumns";
import CareerPage from "../pages/Generic/CareerPage";
import MarketPage from "../pages/Generic/MarketPage";
import MatchingPage from "../pages/Generic/MatchingPage";
import ProfilePage from "../pages/Generic/ProfilePage";
import ResumesPage from "../pages/Resume/ResumesPage";
import ATSPage from "../pages/Resume/ATSPage";

const resource = (title, description, endpoint, emptyText, extra = {}) => (
  <ResourcePage title={title} description={description} endpoint={endpoint} columns={defaultColumns} emptyText={emptyText} {...extra} />
);

const AppRoutes = () => (
  <Routes>
    <Route path="/" element={<Navigate to="/dashboard" replace />} />
    <Route path="/login" element={<Login />} />
    <Route path="/register" element={<Register />} />
    <Route path="/forgot-password" element={<ForgotPassword />} />
    <Route path="/reset-password" element={<ResetPassword />} />
    <Route path="/verify-email" element={<VerifyEmail />} />

    <Route element={<ProtectedRoute />}>
      <Route element={<AppShell />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/pipeline" element={<Pipeline />} />
        <Route path="/resumes" element={<ResumesPage />} />
        <Route path="/ats" element={<ATSPage />} />
        <Route path="/jobs" element={<ResourcePage title="Jobs" description="Discovered and saved job opportunities." endpoint={endpoints.jobs} columns={jobColumns} emptyText="Run the pipeline to discover jobs." />} />
        <Route path="/matching" element={<MatchingPage />} />
        <Route path="/applications" element={resource("Applications", "Track application status and follow-ups.", endpoints.applications, "Applications created by apply actions will appear here.")} />
        <Route path="/cover-letters" element={resource("Cover Letters", "Generated cover letters.", endpoints.coverLetters, "Generate a cover letter for a saved job and resume.")} />
        <Route path="/interview-prep" element={resource("Interview Prep", "Generated prep kits and practice history.", endpoints.interviewHistory, "Generate a prep kit from a job to begin.")} />
        <Route path="/career" element={<CareerPage />} />
        <Route path="/market" element={<MarketPage />} />
        <Route path="/timeline" element={resource("Timeline", "Chronological AI activity log.", endpoints.timeline, "AI activity will appear as you use the app.")} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/admin" element={resource("Admin", "Platform stats and integration configuration.", endpoints.adminStats, "Admin stats are not available.", { admin: true })} />
      </Route>
    </Route>
  </Routes>
);

export default AppRoutes;
