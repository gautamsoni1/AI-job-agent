import { Link } from "react-router-dom";
import { useState } from "react";
import { authApi } from "../../api/auth";
import { showToast } from "../../store/toastStore";
import AuthLayout, { Input, PrimaryButton } from "./AuthLayout";

const ForgotPassword = () => {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const submit = async (event) => {
    event.preventDefault();
    const normalizedEmail = email.trim();
    if (!normalizedEmail) return showToast("Enter your email address.", "warning");
    setSubmitting(true);
    try {
      const res = await authApi.forgotPassword({ email: normalizedEmail });
      showToast(res.message || "If registered, a reset email has been sent.", "success");
    } finally {
      setSubmitting(false);
    }
  };
  return (
    <AuthLayout title="Reset your password" subtitle="Enter your email and we will send reset instructions." footer={<Link className="font-medium text-[#1F4E79]" to="/login">Back to login</Link>}>
      <form className="space-y-4" onSubmit={submit}>
        <Input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <PrimaryButton disabled={submitting}>{submitting ? "Sending..." : "Send reset link"}</PrimaryButton>
      </form>
    </AuthLayout>
  );
};

export default ForgotPassword;
