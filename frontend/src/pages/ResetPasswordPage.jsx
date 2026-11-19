/**
 * ResetPasswordPage.jsx
 * CricketGPT — Set a new password after clicking the email recovery link.
 *
 * Supabase sends the user back to this page with a recovery token in the URL.
 * The Supabase client (detectSessionInUrl: true) automatically exchanges the
 * token for a temporary session, which we can detect via onAuthStateChange
 * emitting the "PASSWORD_RECOVERY" event.
 */

import { useState, useEffect, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Loader2, ShieldCheck, XCircle } from "lucide-react";
import { supabase } from "../services/supabase";
import AuthLayout from "../components/auth/AuthLayout";
import FormInput from "../components/auth/FormInput";
import AlertBanner from "../components/auth/AlertBanner";

export default function ResetPasswordPage() {
  const navigate = useNavigate();

  const [status, setStatus] = useState("loading"); // loading | ready | success | invalid
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});

  /**
   * Wait for Supabase to emit PASSWORD_RECOVERY (happens when detectSessionInUrl
   * parses the recovery token from the URL hash).
   */
  useEffect(() => {
    // Check if we already have a recovery session from a prior auth state change
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        setStatus("ready");
      }
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event) => {
      if (event === "PASSWORD_RECOVERY") {
        setStatus("ready");
      } else if (event === "SIGNED_OUT") {
        setStatus("invalid");
      }
    });

    // If no recovery event fires within 5 s, treat link as invalid / expired.
    const timer = setTimeout(() => {
      setStatus((prev) => (prev === "loading" ? "invalid" : prev));
    }, 5000);

    return () => {
      subscription.unsubscribe();
      clearTimeout(timer);
    };
  }, []);

  const validate = () => {
    const errs = {};
    if (!password) errs.password = "New password is required.";
    else if (password.length < 8) errs.password = "Password must be at least 8 characters.";
    if (!confirmPassword) errs.confirmPassword = "Please confirm your new password.";
    else if (password !== confirmPassword) errs.confirmPassword = "Passwords do not match.";
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = useCallback(
    async (e) => {
      e.preventDefault();
      setError("");
      if (!validate()) return;

      setLoading(true);
      try {
        const { error: updateError } = await supabase.auth.updateUser({ password });
        if (updateError) throw updateError;
        setStatus("success");
        // After 2 s navigate to login; user must sign in fresh.
        setTimeout(() => navigate("/login", { replace: true }), 2500);
      } catch (err) {
        setError(mapAuthError(err));
      } finally {
        setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [password, confirmPassword, navigate]
  );

  /* ── Loading / detecting recovery token ── */
  if (status === "loading") {
    return (
      <AuthLayout>
        <div className="flex flex-col items-center gap-4 py-8 text-center">
          <Loader2 size={36} className="text-accent animate-spin" />
          <p className="text-blue-100/70 text-sm">Verifying your reset link…</p>
        </div>
      </AuthLayout>
    );
  }

  /* ── Invalid / expired link ── */
  if (status === "invalid") {
    return (
      <AuthLayout>
        <div className="flex flex-col items-center gap-4 py-4 text-center">
          <div className="w-16 h-16 rounded-full bg-red-500/15 border border-red-400/40 flex items-center justify-center">
            <XCircle size={32} className="text-red-300" />
          </div>
          <h2 className="text-white font-bold text-xl">Link invalid or expired</h2>
          <p className="text-blue-100/70 text-sm leading-relaxed max-w-xs">
            This password-reset link has expired or was already used. Request a new one below.
          </p>
          <Link
            to="/forgot-password"
            className="mt-2 inline-flex items-center justify-center gap-2 px-6 py-2.5
                       bg-accent hover:bg-accent-dark text-primary-dark font-bold text-sm
                       rounded-xl transition-all duration-150 active:scale-[0.98]"
          >
            Request New Link
          </Link>
        </div>
      </AuthLayout>
    );
  }

  /* ── Success ── */
  if (status === "success") {
    return (
      <AuthLayout>
        <div className="flex flex-col items-center gap-4 py-4 text-center">
          <div className="w-16 h-16 rounded-full bg-emerald-500/15 border border-emerald-400/40 flex items-center justify-center">
            <ShieldCheck size={32} className="text-emerald-300" />
          </div>
          <h2 className="text-white font-bold text-xl">Password updated!</h2>
          <p className="text-blue-100/70 text-sm">
            Redirecting you to sign in…
          </p>
        </div>
      </AuthLayout>
    );
  }

  /* ── Ready: show the new-password form ── */
  return (
    <AuthLayout>
      <h2 className="text-white font-bold text-xl text-center mb-1">Set new password</h2>
      <p className="text-blue-100/60 text-sm text-center mb-6">
        Choose a strong new password for your account.
      </p>

      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <AlertBanner message={error} variant="error" />

        <FormInput
          id="reset-password"
          label="New Password"
          type="password"
          value={password}
          onChange={(e) => { setPassword(e.target.value); setFieldErrors((p) => ({ ...p, password: "" })); }}
          placeholder="Min. 8 characters"
          autoComplete="new-password"
          required
          disabled={loading}
          error={fieldErrors.password}
        />

        <FormInput
          id="reset-confirm-password"
          label="Confirm New Password"
          type="password"
          value={confirmPassword}
          onChange={(e) => { setConfirmPassword(e.target.value); setFieldErrors((p) => ({ ...p, confirmPassword: "" })); }}
          placeholder="Repeat your new password"
          autoComplete="new-password"
          required
          disabled={loading}
          error={fieldErrors.confirmPassword}
        />

        <button
          type="submit"
          disabled={loading}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 mt-1
                     bg-accent hover:bg-accent-dark text-primary-dark font-bold text-sm
                     rounded-xl shadow-md shadow-yellow-500/20
                     transition-all duration-150 active:scale-[0.98]
                     disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? <Loader2 size={17} className="animate-spin" /> : null}
          Update Password
        </button>
      </form>
    </AuthLayout>
  );
}

function mapAuthError(err) {
  const msg = err?.message ?? "";
  if (msg.includes("New password should be different")) return "New password must be different from your current password.";
  if (msg.includes("network") || msg.includes("fetch")) return "Network error. Check your connection.";
  return msg || "An unexpected error occurred. Please try again.";
}
