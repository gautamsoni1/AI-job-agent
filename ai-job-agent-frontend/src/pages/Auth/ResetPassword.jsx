import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useState } from "react";
import { authApi } from "../../api/auth";
import { showToast } from "../../store/toastStore";
import AuthLayout, { Input, PrimaryButton } from "./AuthLayout";

const ResetPassword = () => {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token")?.trim();
  const [new_password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const submit = async (event) => {
    event.preventDefault();
    if (!token) return showToast("Reset link is invalid. Request a new one.", "danger");
    const password = new_password.trim();
    if (password.length < 8) return showToast("Password must be at least 8 characters", "warning");
    setSubmitting(true);
    try {
      const res = await authApi.resetPassword({ token, new_password: password });
      showToast(res.message || "Password reset complete", "success");
      navigate("/login", { replace: true });
    } finally {
      setSubmitting(false);
    }
  };

  if (!token) {
    return (
      <AuthLayout
        title="Reset link is invalid"
        subtitle="This link does not contain a reset token. Request a fresh password reset email."
        footer={<Link className="font-medium text-[#1F4E79]" to="/forgot-password">Request a new link</Link>}
      >
        <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          The password reset link is incomplete or invalid.
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Choose a new password" subtitle="Use the reset token from your email." footer={<Link className="font-medium text-[#1F4E79]" to="/login">Back to login</Link>}>
      <form className="space-y-4" onSubmit={submit}>
        <Input type="password" placeholder="New password" value={new_password} onChange={(e) => setPassword(e.target.value)} required />
        <PrimaryButton disabled={submitting}>{submitting ? "Updating..." : "Update password"}</PrimaryButton>
      </form>
    </AuthLayout>
  );
};

export default ResetPassword;
