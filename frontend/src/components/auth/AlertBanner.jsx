/**
 * AlertBanner.jsx
 * Inline alert for auth feedback (errors, success notices).
 */

import { AlertCircle, CheckCircle, Info } from "lucide-react";

const VARIANTS = {
  error: {
    icon: AlertCircle,
    classes: "bg-red-500/15 border-red-400/40 text-red-200",
  },
  success: {
    icon: CheckCircle,
    classes: "bg-emerald-500/15 border-emerald-400/40 text-emerald-200",
  },
  info: {
    icon: Info,
    classes: "bg-blue-500/15 border-blue-400/40 text-blue-200",
  },
};

/**
 * @param {{ message: string, variant?: 'error'|'success'|'info' }} props
 */
export default function AlertBanner({ message, variant = "error" }) {
  if (!message) return null;
  const { icon: Icon, classes } = VARIANTS[variant] ?? VARIANTS.error;

  return (
    <div
      role="alert"
      className={`flex items-start gap-2.5 px-4 py-3 rounded-xl border text-sm font-medium animate-fade-in ${classes}`}
    >
      <Icon size={16} className="flex-shrink-0 mt-0.5" />
      <span>{message}</span>
    </div>
  );
}
