/**
 * ForgotPasswordPage.jsx
 * CricketGPT — Send password-reset email via Supabase.
 */

import { useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { Loader2, ArrowLeft, MailCheck } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import AuthLayout from "../components/auth/AuthLayout";
import FormInput from "../components/auth/FormInput";
import AlertBanner from "../components/auth/AlertBanner";

function validateEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

export default function ForgotPasswordPage() {
  const { resetPassword } = useAuth();

  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [sent, setSent] = useState(false);

  const handleSubmit = useCallback(
    async (e) => {
      e.preventDefault();
      setError("");
      setFieldError("");

      if (!email.trim()) {
        setFieldError("Email is required.");
        return;
      }
      if (!validateEmail(email)) {
        setFieldError("Enter a valid email address.");
        return;
      }

      setLoading(true);
      try {
        await resetPassword(email.trim());
        setSent(true);
      } catch (err) {
        setError(mapAuthError(err));
      } finally {
        setLoading(false);
      }
    },
    [email, resetPassword]
  );

  /* ── Success state ── */
  if (sent) {
    return (
      <AuthLayout>
        <div className="flex flex-col items-center gap-4 text-center py-4">
          <div className="w-16 h-16 rounded-full bg-emerald-500/15 border border-emerald-400/40 flex items-center justify-center">
            <MailCheck size={32} className="text-emerald-300" />
          </div>
          <h2 className="text-white font-bold text-xl">Reset link sent</h2>
          <p className="text-blue-100/70 text-sm leading-relaxed max-w-xs">
            If an account exists for{" "}
            <span className="text-accent font-semibold">{email}</span>, you&apos;ll
            receive a password-reset link shortly. Check your spam folder too.
          </p>
          <Link
            to="/login"
            className="mt-2 inline-flex items-center justify-center gap-2 px-6 py-2.5
                       bg-accent hover:bg-accent-dark text-primary-dark font-bold text-sm
                       rounded-xl transition-all duration-150 active:scale-[0.98]"
          >
            Back to Sign In
          </Link>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <h2 className="text-white font-bold text-xl text-center mb-1">Forgot password?</h2>
      <p className="text-blue-100/60 text-sm text-center mb-6">
        Enter your email and we&apos;ll send you a reset link.
      </p>

      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <AlertBanner message={error} variant="error" />

        <FormInput
          id="forgot-email"
          label="Email"
          type="email"
          value={email}
          onChange={(e) => { setEmail(e.target.value); setFieldError(""); }}
          placeholder="you@example.com"
          autoComplete="email"
          required
          disabled={loading}
          error={fieldError}
        />

        <button
          type="submit"
          disabled={loading}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5
                     bg-accent hover:bg-accent-dark text-primary-dark font-bold text-sm
                     rounded-xl shadow-md shadow-yellow-500/20
                     transition-all duration-150 active:scale-[0.98]
                     disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? <Loader2 size={17} className="animate-spin" /> : null}
          Send Reset Link
        </button>
      </form>

      <div className="mt-6 flex justify-center">
        <Link
          to="/login"
          className="inline-flex items-center gap-1.5 text-blue-100/60 hover:text-white text-sm font-medium transition-colors duration-150"
        >
          <ArrowLeft size={14} />
          Back to Sign In
        </Link>
      </div>
    </AuthLayout>
  );
}

function mapAuthError(err) {
  const msg = err?.message ?? "";
  if (msg.includes("Too many requests")) return "Too many attempts. Please wait a moment.";
  if (msg.includes("network") || msg.includes("fetch")) return "Network error. Check your connection.";
  return msg || "An unexpected error occurred. Please try again.";
}
