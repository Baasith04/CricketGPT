/**
 * router.jsx — CricketGPT client-side routing.
 *
 * Route guards:
 *   <PrivateRoute>   — requires a signed-in user; redirects to /login otherwise.
 *   <PublicOnlyRoute> — redirects authenticated users away from auth pages to /.
 *
 * Both wait for the AuthContext "loading" flag to resolve before redirecting so
 * that a page-refresh doesn't flash the wrong screen.
 */

import { createBrowserRouter, Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./context/AuthContext";

import App from "./App";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import AccountPage from "./pages/AccountPage";

/* ── Spinner shown while session is being resolved ── */
function AuthLoadingScreen() {
  return (
    <div className="app-bg min-h-screen flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div
          className="w-12 h-12 rounded-full border-4 border-accent/30 border-t-accent animate-spin"
          aria-label="Loading…"
        />
        <p className="text-blue-100/60 text-sm font-medium">Loading CricketGPT…</p>
      </div>
    </div>
  );
}

/** Wraps routes that require authentication. */
function PrivateRoute() {
  const { user, loading } = useAuth();
  if (loading) return <AuthLoadingScreen />;
  return user ? <Outlet /> : <Navigate to="/login" replace />;
}

/** Wraps auth pages — bounces signed-in users back to the app. */
function PublicOnlyRoute() {
  const { user, loading } = useAuth();
  if (loading) return <AuthLoadingScreen />;
  return user ? <Navigate to="/" replace /> : <Outlet />;
}

export const router = createBrowserRouter([
  {
    /* ── Protected: main app ── */
    element: <PrivateRoute />,
    children: [
      { path: "/", element: <App /> },
      { path: "/account", element: <AccountPage /> },
    ],
  },
  {
    /* ── Public-only: auth pages ── */
    element: <PublicOnlyRoute />,
    children: [
      { path: "/login", element: <LoginPage /> },
      { path: "/signup", element: <SignupPage /> },
      { path: "/forgot-password", element: <ForgotPasswordPage /> },
    ],
  },
  {
    /* Reset password is always accessible (token in URL hash) */
    path: "/reset-password",
    element: <ResetPasswordPage />,
  },
  {
    /* Fallback: send unknown paths to the root (which may then redirect to login) */
    path: "*",
    element: <Navigate to="/" replace />,
  },
]);
