/**
 * AvatarUpload.jsx
 * Circular avatar display with click-to-upload.
 * Gracefully reports missing bucket setup rather than silently failing.
 */

import { useRef, useState } from "react";
import { Camera, Loader2, User } from "lucide-react";
import AlertBanner from "../auth/AlertBanner";

/**
 * @param {{
 *   avatarUrl: string | null,
 *   displayName: string,
 *   onUpload: (file: File) => Promise<void>,
 * }} props
 */
export default function AvatarUpload({ avatarUrl, displayName, onUpload }) {
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const initials = (displayName ?? "")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    // Reset input so the same file can be re-selected after an error
    e.target.value = "";
    setError("");
    setUploading(true);
    try {
      await onUpload(file);
    } catch (err) {
      setError(err?.message ?? "Upload failed.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="flex flex-col items-center gap-4">
      {/* Avatar circle */}
      <div className="relative group">
        <div
          className="w-24 h-24 rounded-full border-2 border-accent/60 shadow-lg shadow-blue-950/40
                     overflow-hidden bg-primary flex items-center justify-center select-none"
        >
          {avatarUrl ? (
            <img
              src={avatarUrl}
              alt={displayName ?? "Avatar"}
              className="w-full h-full object-cover"
            />
          ) : initials ? (
            <span className="text-white font-bold text-3xl">{initials}</span>
          ) : (
            <User size={36} className="text-blue-100/60" />
          )}

          {/* Hover overlay */}
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={uploading}
            aria-label="Upload profile picture"
            className="absolute inset-0 bg-primary-dark/70 flex items-center justify-center
                       opacity-0 group-hover:opacity-100 transition-opacity duration-200
                       disabled:cursor-not-allowed"
          >
            {uploading ? (
              <Loader2 size={22} className="text-accent animate-spin" />
            ) : (
              <Camera size={22} className="text-white" />
            )}
          </button>
        </div>
      </div>

      {/* Hidden file input */}
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        className="hidden"
        onChange={handleFileChange}
      />

      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
        className="text-xs text-accent/80 hover:text-accent font-semibold
                   transition-colors duration-150 disabled:opacity-50"
      >
        {uploading ? "Uploading…" : "Change photo"}
      </button>

      {error && <AlertBanner message={error} variant="error" />}
    </div>
  );
}
