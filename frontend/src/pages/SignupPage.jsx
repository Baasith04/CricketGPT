/**
 * SignupPage.jsx
 * CricketGPT — Email / Google account creation.
 */

import { useState, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Loader2, CheckCircle } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import AuthLayout from "../components/auth/AuthLayout";
import FormInput from "../components/auth/FormInput";
import GoogleButton from "../components/auth/GoogleButton";
import AlertBanner from "../components/auth/AlertBanner";

function validateEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

/** Basic password strength rules */
function getPasswordStrength(pw) {
  if (!pw) return { score: 0, label: "", color: "" };
  let score = 0;
  if (pw.length >= 8) score++;
  if (/[A-Z]/.test(pw)) score++;
  if (/[0-9]/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  if (score <= 1) return { score, label: "Weak", color: "bg-red-400" };
  if (score === 2) return { score, label: "Fair", color: "bg-amber-400" };
  if (score === 3) return { score, label: "Good", color: "bg-blue-400" };
  return { score, label: "Strong", color: "bg-emerald-400" };
}

export default function SignupPage() {
  const navigate = useNavigate();
  const { signUp, signInWithGoogle } = useAuth();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [emailSent, setEmailSent] = useState(false);

  const strength = getPasswordStrength(password);

  const validate = () => {
    const errs = {};
    if (!fullName.trim()) errs.fullName = "Full name is required.";
    else if (fullName.trim().length < 2) errs.fullName = "Name must be at least 2 characters.";

    if (!email.trim()) errs.email = "Email is required.";
    else if (!validateEmail(email)) errs.email = "Enter a valid email address.";

    if (!password) errs.password = "Password is required.";
    else if (password.length < 8) errs.password = "Password must be at least 8 characters.";

    if (!confirmPassword) errs.confirmPassword = "Please confirm your password.";
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
        const data = await signUp(fullName.trim(), email.trim(), password);
        // If Supabase returns a session immediately, navigate; otherwise show email notice.
        if (data?.session) {
          navigate("/", { replace: true });
        } else {
          setEmailSent(true);
        }
      } catch (err) {
        setError(mapAuthError(err));
      } finally {
        setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [fullName, email, password, confirmPassword, signUp, navigate]
  );

  const handleGoogle = useCallback(async () => {
    setError("");
    setGoogleLoading(true);
    try {
      await signInWithGoogle();
    } catch (err) {
      setError(mapAuthError(err));
      setGoogleLoading(false);
    }
  }, [signInWithGoogle]);

  /* ── Email confirmation success state ── */
  if (emailSent) {
    return (
      <AuthLayout>
        <div className="flex flex-col items-center gap-4 text-center py-4">
          <div className="w-16 h-16 rounded-full bg-emerald-500/15 border border-emerald-400/40 flex items-center justify-center">
            <CheckCircle size={32} className="text-emerald-300" />
          </div>
          <h2 className="text-white font-bold text-xl">Check your inbox</h2>
          <p className="text-blue-100/70 text-sm leading-relaxed max-w-xs">
            We&apos;ve sent a confirmation link to{" "}
            <span className="text-accent font-semibold">{email}</span>.{" "}
            Click it to activate your account, then sign in.
          </p>
          <Link
            to="/login"
            className="mt-2 inline-flex items-center justify-center gap-2 px-6 py-2.5
                       bg-accent hover:bg-accent-dark text-primary-dark font-bold text-sm
                       rounded-xl transition-all duration-150 active:scale-[0.98]"
          >
            Go to Sign In
          </Link>
        </div>
      </AuthLayout>
    );
  }

  const busy = loading || googleLoading;

  return (
    <AuthLayout>
      <h2 className="text-white font-bold text-xl text-center mb-1">Create account</h2>
      <p className="text-blue-100/60 text-sm text-center mb-6">
        Join CricketGPT — it&apos;s free
      </p>

      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <AlertBanner message={error} variant="error" />

        <FormInput
          id="signup-name"
          label="Full Name"
          type="text"
          value={fullName}
          onChange={(e) => { setFullName(e.target.value); setFieldErrors((p) => ({ ...p, fullName: "" })); }}
          placeholder="Enter your name"
          autoComplete="name"
          required
          disabled={busy}
          error={fieldErrors.fullName}
        />

        <FormInput
          id="signup-email"
          label="Email"
          type="email"
          value={email}
          onChange={(e) => { setEmail(e.target.value); setFieldErrors((p) => ({ ...p, email: "" })); }}
          placeholder="you@example.com"
          autoComplete="email"
          required
          disabled={busy}
          error={fieldErrors.email}
        />

        <div className="flex flex-col gap-1.5">
          <FormInput
            id="signup-password"
            label="Password"
            type="password"
            value={password}
            onChange={(e) => { setPassword(e.target.value); setFieldErrors((p) => ({ ...p, password: "" })); }}
            placeholder="Min. 8 characters"
            autoComplete="new-password"
            required
            disabled={busy}
            error={fieldErrors.password}
          />
          {/* Strength bar */}
          {password && (
            <div className="flex items-center gap-2 mt-0.5">
              <div className="flex-1 h-1.5 rounded-full bg-white/10 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-300 ${strength.color}`}
                  style={{ width: `${(strength.score / 4) * 100}%` }}
                />
              </div>
              <span className="text-xs text-blue-100/60 font-medium w-10 text-right">
                {strength.label}
              </span>
            </div>
          )}
        </div>

        <FormInput
          id="signup-confirm-password"
          label="Confirm Password"
          type="password"
          value={confirmPassword}
          onChange={(e) => { setConfirmPassword(e.target.value); setFieldErrors((p) => ({ ...p, confirmPassword: "" })); }}
          placeholder="Repeat your password"
          autoComplete="new-password"
          required
          disabled={busy}
          error={fieldErrors.confirmPassword}
        />

        <button
          type="submit"
          disabled={busy}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 mt-1
                     bg-accent hover:bg-accent-dark text-primary-dark font-bold text-sm
                     rounded-xl shadow-md shadow-yellow-500/20
                     transition-all duration-150 active:scale-[0.98]
                     disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? <Loader2 size={17} className="animate-spin" /> : null}
          Create Account
        </button>
      </form>

      {/* Divider */}
      <div className="flex items-center gap-3 my-5">
        <span className="flex-1 h-px bg-white/15" />
        <span className="text-blue-100/50 text-xs font-medium">or</span>
        <span className="flex-1 h-px bg-white/15" />
      </div>

      <GoogleButton onClick={handleGoogle} loading={googleLoading} disabled={busy} />

      <p className="text-center text-blue-100/55 text-sm mt-7">
        Already have an account?{" "}
        <Link
          to="/login"
          className="text-accent font-semibold hover:text-accent-dark transition-colors duration-150"
        >
          Sign in
        </Link>
      </p>
    </AuthLayout>
  );
}

function mapAuthError(err) {
  const msg = err?.message ?? "";
  if (msg.includes("User already registered")) return "An account with this email already exists. Try signing in.";
  if (msg.includes("Password should be")) return "Password must be at least 6 characters.";
  if (msg.includes("Too many requests")) return "Too many attempts. Please wait a moment and try again.";
  if (msg.includes("network") || msg.includes("fetch")) return "Network error. Check your connection and try again.";
  return msg || "An unexpected error occurred. Please try again.";
}
