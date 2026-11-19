/**
 * LoginPage.jsx
 * CricketGPT — Email / Google sign-in.
 */

import { useState, useCallback } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import AuthLayout from "../components/auth/AuthLayout";
import FormInput from "../components/auth/FormInput";
import GoogleButton from "../components/auth/GoogleButton";
import AlertBanner from "../components/auth/AlertBanner";

function validateEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

export default function LoginPage() {
  const navigate = useNavigate();
  const { signIn, signInWithGoogle } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});

  const validate = () => {
    const errs = {};
    if (!email.trim()) errs.email = "Email is required.";
    else if (!validateEmail(email)) errs.email = "Enter a valid email address.";
    if (!password) errs.password = "Password is required.";
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
        await signIn(email.trim(), password);
        navigate("/", { replace: true });
      } catch (err) {
        setError(mapAuthError(err));
      } finally {
        setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [email, password, signIn, navigate]
  );

  const handleGoogle = useCallback(async () => {
    setError("");
    setGoogleLoading(true);
    try {
      await signInWithGoogle();
      // Supabase redirects the browser; no manual navigate needed.
    } catch (err) {
      setError(mapAuthError(err));
      setGoogleLoading(false);
    }
  }, [signInWithGoogle]);

  const busy = loading || googleLoading;

  return (
    <AuthLayout>
      <h2 className="text-white font-bold text-xl text-center mb-1">Welcome back</h2>
      <p className="text-blue-100/60 text-sm text-center mb-6">
        Sign in to your CricketGPT account
      </p>

      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <AlertBanner message={error} variant="error" />

        <FormInput
          id="login-email"
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

        <FormInput
          id="login-password"
          label="Password"
          type="password"
          value={password}
          onChange={(e) => { setPassword(e.target.value); setFieldErrors((p) => ({ ...p, password: "" })); }}
          placeholder="Your password"
          autoComplete="current-password"
          required
          disabled={busy}
          error={fieldErrors.password}
        />

        {/* Forgot password */}
        <div className="flex justify-end -mt-1">
          <Link
            to="/forgot-password"
            className="text-xs text-accent/80 hover:text-accent font-semibold transition-colors duration-150"
          >
            Forgot password?
          </Link>
        </div>

        <button
          type="submit"
          disabled={busy}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5
                     bg-accent hover:bg-accent-dark text-primary-dark font-bold text-sm
                     rounded-xl shadow-md shadow-yellow-500/20
                     transition-all duration-150 active:scale-[0.98]
                     disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? <Loader2 size={17} className="animate-spin" /> : null}
          Sign In
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
        Don&apos;t have an account?{" "}
        <Link
          to="/signup"
          className="text-accent font-semibold hover:text-accent-dark transition-colors duration-150"
        >
          Create one
        </Link>
      </p>
    </AuthLayout>
  );
}

/** Map Supabase auth error messages to user-friendly strings. */
function mapAuthError(err) {
  const msg = err?.message ?? "";
  if (msg.includes("Invalid login credentials")) return "Incorrect email or password. If New User, Please Create Account";
  if (msg.includes("Email not confirmed")) return "Please confirm your email before signing in.";
  if (msg.includes("Too many requests")) return "Too many attempts. Please wait a moment and try again.";
  if (msg.includes("network") || msg.includes("fetch")) return "Network error. Check your connection and try again.";
  return msg || "An unexpected error occurred. Please try again.";
}
