/**
 * FormInput.jsx
 * Reusable controlled input for auth forms.
 * Supports show/hide toggle for password fields.
 */

import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

/**
 * @param {{
 *   id: string,
 *   label: string,
 *   type?: string,
 *   value: string,
 *   onChange: (e: React.ChangeEvent<HTMLInputElement>) => void,
 *   placeholder?: string,
 *   autoComplete?: string,
 *   required?: boolean,
 *   disabled?: boolean,
 *   error?: string,
 * }} props
 */
export default function FormInput({
  id,
  label,
  type = "text",
  value,
  onChange,
  placeholder = "",
  autoComplete,
  required = false,
  disabled = false,
  error,
}) {
  const isPassword = type === "password";
  const [showPassword, setShowPassword] = useState(false);
  const inputType = isPassword ? (showPassword ? "text" : "password") : type;

  return (
    <div className="flex flex-col gap-1.5">
      <label
        htmlFor={id}
        className="text-blue-100/90 text-xs font-semibold uppercase tracking-wider"
      >
        {label}
        {required && <span className="text-accent ml-0.5">*</span>}
      </label>

      <div className="relative">
        <input
          id={id}
          type={inputType}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          autoComplete={autoComplete}
          required={required}
          disabled={disabled}
          aria-invalid={!!error}
          aria-describedby={error ? `${id}-error` : undefined}
          className={`w-full bg-white/8 text-white placeholder-blue-100/40
                      border rounded-xl px-4 py-2.5 text-sm font-medium
                      focus:outline-none focus:ring-2 focus:ring-accent/70 focus:border-accent/60
                      transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed
                      ${isPassword ? "pr-11" : ""}
                      ${
                        error
                          ? "border-red-400/60 bg-red-500/5"
                          : "border-white/20 hover:border-white/35"
                      }`}
        />

        {isPassword && (
          <button
            type="button"
            tabIndex={-1}
            onClick={() => setShowPassword((v) => !v)}
            aria-label={showPassword ? "Hide password" : "Show password"}
            className="absolute right-3 top-1/2 -translate-y-1/2
                       text-blue-100/60 hover:text-white transition-colors duration-150"
          >
            {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        )}
      </div>

      {error && (
        <p id={`${id}-error`} role="alert" className="text-red-300 text-xs font-medium">
          {error}
        </p>
      )}
    </div>
  );
}
