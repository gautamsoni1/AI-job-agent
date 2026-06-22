import { Link, useSearchParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { authApi } from "../../api/auth";
import AuthLayout from "./AuthLayout";

const VerifyEmail = () => {
  const [params] = useSearchParams();
  const [message, setMessage] = useState("Verifying your email...");

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      queueMicrotask(() => setMessage("Verification token is missing."));
      return;
    }
    authApi.verifyEmail(token).then((res) => setMessage(res.message || "Email verified.")).catch(() => setMessage("Verification failed."));
  }, [params]);

  return (
    <AuthLayout title="Email verification" subtitle={message} footer={<Link className="font-medium text-[#1F4E79]" to="/login">Continue to login</Link>}>
      <div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">{message}</div>
    </AuthLayout>
  );
};

export default VerifyEmail;
