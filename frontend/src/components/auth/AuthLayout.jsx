/**
 * AuthLayout.jsx
 * Shared wrapper for all auth pages (Login, Signup, ForgotPassword, ResetPassword).
 * Renders the same stadium background as the main app, plus a centred glass card.
 */

export default function AuthLayout({ children }) {
  return (
    <div className="app-bg min-h-screen flex items-center justify-center px-4 py-8">
      {/* Glass card */}
      <div
        className="w-full max-w-md bg-primary-dark/80 backdrop-blur-xl
                   border border-white/15 rounded-3xl shadow-2xl shadow-blue-950/60
                   px-7 py-9 sm:px-10 sm:py-11 animate-fade-in"
      >
        {/* Logo / branding */}
        <div className="flex flex-col items-center mb-8">
          <div
            className="w-14 h-14 rounded-full bg-primary flex items-center justify-center
                       shadow-lg shadow-blue-950/60 border-2 border-accent/80 overflow-hidden mb-3"
          >
            <img
              src="/cricket-ball.svg"
              alt="CricketGPT logo"
              className="w-9 h-9 select-none"
            />
          </div>
          <h1 className="text-white font-extrabold text-2xl leading-tight tracking-tight">
            Cricket<span className="text-accent">GPT</span>
          </h1>
          <p className="text-blue-100/70 text-xs font-medium mt-0.5">
            Your AI-powered IPL assistant
          </p>
        </div>

        {children}
      </div>
    </div>
  );
}
