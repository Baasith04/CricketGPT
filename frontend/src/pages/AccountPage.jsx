/**
 * AccountPage.jsx
 * /account — Profile management, password change, email change.
 *
 * Sections:
 *   1. Profile Overview  — read-only info card (email, provider, joined date)
 *   2. Profile Details   — avatar + editable full name
 *   3. Change Password   — only shown for email/password accounts
 *   4. Change Email      — request email update with Supabase confirmation flow
 */

import { useState, useCallback } from "react";
import { Loader2, Shield, Mail, Calendar, User as UserIcon } from "lucide-react";
import { supabase } from "../services/supabase";
import { useAuth } from "../context/AuthContext";
import { useProfile } from "../hooks/useProfile";
import AccountLayout from "../components/account/AccountLayout";
import SettingsCard from "../components/account/SettingsCard";
import AvatarUpload from "../components/account/AvatarUpload";
import FormInput from "../components/auth/FormInput";
import AlertBanner from "../components/auth/AlertBanner";

/* ─── Helpers ─── */

function formatDate(dateStr) {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function validateEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

function mapError(err) {
  const msg = err?.message ?? "";
  if (msg.includes("New password should be different")) return "New password must differ from your current one.";
  if (msg.includes("Password should be at least")) return "Password must be at least 6 characters.";
  if (msg.includes("requires recent login") || msg.includes("reauthentication"))
    return "For security, please sign out and sign back in before changing your email.";
  if (msg.includes("User already registered") || msg.includes("already been registered"))
    return "That email address is already in use.";
  if (msg.includes("network") || msg.includes("fetch")) return "Network error — check your connection.";
  return msg || "An unexpected error occurred.";
}

/* ─── Sub-sections ─── */

/** 1 · Profile Overview — read-only identity information */
function ProfileOverviewSection({ user, profile, profileLoading }) {
  const provider = user?.app_metadata?.provider ?? "email";
  const isGoogle = provider === "google";

  const InfoRow = ({ icon: Icon, label, value }) => (
    <div className="flex items-center gap-3 py-3 border-b border-white/8 last:border-0">
      <div className="w-8 h-8 rounded-lg bg-primary/40 flex items-center justify-center flex-shrink-0">
        <Icon size={15} className="text-blue-300" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-blue-100/50 text-[11px] uppercase tracking-wider font-semibold">{label}</p>
        <p className="text-white text-sm font-medium mt-0.5 truncate">
          {profileLoading ? (
            <span className="inline-block w-32 h-3.5 rounded bg-white/10 animate-pulse" />
          ) : (
            value
          )}
        </p>
      </div>
    </div>
  );

  return (
    <SettingsCard
      title="Account Information"
      description="Your identity and registration details."
    >
      <InfoRow icon={Mail} label="Email address" value={user?.email ?? "—"} />
      <InfoRow
        icon={Shield}
        label="Sign-in method"
        value={
          isGoogle ? (
            <span className="inline-flex items-center gap-1.5">
              <svg width="13" height="13" viewBox="0 0 18 18" aria-hidden="true">
                <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615Z" />
                <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18Z" />
                <path fill="#FBBC05" d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332Z" />
                <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58Z" />
              </svg>
              Google
            </span>
          ) : (
            "Email & Password"
          )
        }
      />
      <InfoRow
        icon={Calendar}
        label="Member since"
        value={formatDate(profile?.created_at ?? user?.created_at)}
      />
    </SettingsCard>
  );
}

/** 2 · Profile Details — avatar + editable full name */
function ProfileDetailsSection({ profile, profileLoading, profileError, updateFullName, uploadAvatar }) {
  const [editing, setEditing] = useState(false);
  const [nameValue, setNameValue] = useState("");
  const [nameError, setNameError] = useState("");
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");

  const startEditing = () => {
    setNameValue(profile?.full_name ?? "");
    setNameError("");
    setError("");
    setSuccess("");
    setEditing(true);
  };

  const handleSave = useCallback(async () => {
    setNameError("");
    setError("");
    setSuccess("");
    const trimmed = nameValue.trim();
    if (!trimmed) { setNameError("Name cannot be empty."); return; }
    if (trimmed.length < 2) { setNameError("Name must be at least 2 characters."); return; }

    setSaving(true);
    try {
      await updateFullName(trimmed);
      setSuccess("Name updated successfully.");
      setEditing(false);
    } catch (err) {
      setError(mapError(err));
    } finally {
      setSaving(false);
    }
  }, [nameValue, updateFullName]);

  const handleAvatarUpload = useCallback(async (file) => {
    setError("");
    setSuccess("");
    await uploadAvatar(file);
    setSuccess("Profile picture updated.");
  }, [uploadAvatar]);

  if (profileLoading) {
    return (
      <SettingsCard title="Profile" description="Your public display name and picture.">
        <div className="flex items-center justify-center py-6">
          <Loader2 size={24} className="text-accent animate-spin" />
        </div>
      </SettingsCard>
    );
  }

  return (
    <SettingsCard title="Profile" description="Your public display name and picture.">
      {profileError && (
        <div className="mb-4">
          <AlertBanner message={profileError} variant="error" />
        </div>
      )}

      <div className="flex flex-col sm:flex-row gap-6 sm:gap-8 items-start">
        {/* Avatar */}
        <div className="flex-shrink-0 self-center sm:self-start">
          <AvatarUpload
            avatarUrl={profile?.avatar_url}
            displayName={profile?.full_name ?? ""}
            onUpload={handleAvatarUpload}
          />
        </div>

        {/* Name field */}
        <div className="flex-1 w-full flex flex-col gap-4">
          <AlertBanner message={error} variant="error" />
          <AlertBanner message={success} variant="success" />

          {editing ? (
            <div className="flex flex-col gap-3">
              <FormInput
                id="account-full-name"
                label="Full Name"
                type="text"
                value={nameValue}
                onChange={(e) => { setNameValue(e.target.value); setNameError(""); }}
                placeholder="Your full name"
                autoComplete="name"
                required
                disabled={saving}
                error={nameError}
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saving}
                  className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-dark
                             text-primary-dark font-bold text-sm rounded-xl
                             transition-all duration-150 active:scale-95
                             disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {saving && <Loader2 size={14} className="animate-spin" />}
                  Save
                </button>
                <button
                  type="button"
                  onClick={() => setEditing(false)}
                  disabled={saving}
                  className="px-4 py-2 text-blue-100/70 hover:text-white text-sm font-semibold
                             bg-white/8 hover:bg-white/15 border border-white/15 rounded-xl
                             transition-all duration-150 disabled:opacity-50"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-1">
              <p className="text-blue-100/50 text-xs uppercase tracking-wider font-semibold">
                Full Name
              </p>
              <div className="flex items-center gap-3">
                <p className="text-white text-base font-semibold">
                  {profile?.full_name || (
                    <span className="text-blue-100/40 italic">Not set</span>
                  )}
                </p>
                <button
                  type="button"
                  onClick={startEditing}
                  className="text-xs text-accent/80 hover:text-accent font-semibold
                             transition-colors duration-150"
                >
                  Edit
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </SettingsCard>
  );
}

/** 3 · Change Password — only for email/password users */
function ChangePasswordSection({ user }) {
  const provider = user?.app_metadata?.provider ?? "email";
  const isGoogle = provider === "google";

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});

  if (isGoogle) {
    return (
      <SettingsCard
        title="Password"
        description="Password management is not available for Google sign-in accounts."
      >
        <p className="text-blue-100/50 text-sm">
          Your account uses Google authentication. Password changes are managed through your Google account settings.
        </p>
      </SettingsCard>
    );
  }

  const validate = () => {
    const errs = {};
    if (!currentPassword) errs.currentPassword = "Current password is required.";
    if (!newPassword) errs.newPassword = "New password is required.";
    else if (newPassword.length < 8) errs.newPassword = "Password must be at least 8 characters.";
    if (!confirmPassword) errs.confirmPassword = "Please confirm your new password.";
    else if (newPassword !== confirmPassword) errs.confirmPassword = "Passwords do not match.";
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    if (!validate()) return;

    setSaving(true);
    try {
      // Re-authenticate first so Supabase accepts the password change
      const { error: signInErr } = await supabase.auth.signInWithPassword({
        email: user.email,
        password: currentPassword,
      });
      if (signInErr) {
        setFieldErrors((p) => ({ ...p, currentPassword: "Incorrect current password." }));
        return;
      }

      const { error: updateErr } = await supabase.auth.updateUser({ password: newPassword });
      if (updateErr) throw updateErr;

      setSuccess("Password updated successfully.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setFieldErrors({});
    } catch (err) {
      setError(mapError(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <SettingsCard
      title="Change Password"
      description="Use a strong password of at least 8 characters."
    >
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4 max-w-md">
        <AlertBanner message={error} variant="error" />
        <AlertBanner message={success} variant="success" />

        <FormInput
          id="acc-current-pw"
          label="Current Password"
          type="password"
          value={currentPassword}
          onChange={(e) => { setCurrentPassword(e.target.value); setFieldErrors((p) => ({ ...p, currentPassword: "" })); }}
          placeholder="Your current password"
          autoComplete="current-password"
          required
          disabled={saving}
          error={fieldErrors.currentPassword}
        />
        <FormInput
          id="acc-new-pw"
          label="New Password"
          type="password"
          value={newPassword}
          onChange={(e) => { setNewPassword(e.target.value); setFieldErrors((p) => ({ ...p, newPassword: "" })); }}
          placeholder="Min. 8 characters"
          autoComplete="new-password"
          required
          disabled={saving}
          error={fieldErrors.newPassword}
        />
        <FormInput
          id="acc-confirm-pw"
          label="Confirm New Password"
          type="password"
          value={confirmPassword}
          onChange={(e) => { setConfirmPassword(e.target.value); setFieldErrors((p) => ({ ...p, confirmPassword: "" })); }}
          placeholder="Repeat your new password"
          autoComplete="new-password"
          required
          disabled={saving}
          error={fieldErrors.confirmPassword}
        />

        <button
          type="submit"
          disabled={saving}
          className="self-start flex items-center gap-2 px-5 py-2.5
                     bg-accent hover:bg-accent-dark text-primary-dark font-bold text-sm
                     rounded-xl shadow-md shadow-yellow-500/20
                     transition-all duration-150 active:scale-95
                     disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving && <Loader2 size={15} className="animate-spin" />}
          Update Password
        </button>
      </form>
    </SettingsCard>
  );
}

/** 4 · Change Email */
function ChangeEmailSection({ user }) {
  const [newEmail, setNewEmail] = useState("");
  const [emailError, setEmailError] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setEmailError("");

    if (!newEmail.trim()) { setEmailError("Email is required."); return; }
    if (!validateEmail(newEmail)) { setEmailError("Enter a valid email address."); return; }
    if (newEmail.trim().toLowerCase() === user?.email?.toLowerCase()) {
      setEmailError("That's already your current email address.");
      return;
    }

    setSaving(true);
    try {
      const { error: updateErr } = await supabase.auth.updateUser({
        email: newEmail.trim(),
      });
      if (updateErr) throw updateErr;

      setSuccess(
        "Confirmation emails have been sent to both your old and new address. Click the link in both to complete the change."
      );
      setNewEmail("");
    } catch (err) {
      setError(mapError(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <SettingsCard
      title="Change Email"
      description="A confirmation will be sent to both your current and new address."
    >
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4 max-w-md">
        {/* Current email (read-only display) */}
        <div className="flex flex-col gap-1.5">
          <p className="text-blue-100/50 text-xs uppercase tracking-wider font-semibold">Current Email</p>
          <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-white/15 bg-white/5">
            <Mail size={14} className="text-blue-300 flex-shrink-0" />
            <span className="text-white/80 text-sm font-medium">{user?.email}</span>
          </div>
        </div>

        <AlertBanner message={error} variant="error" />
        <AlertBanner message={success} variant="success" />

        <FormInput
          id="acc-new-email"
          label="New Email Address"
          type="email"
          value={newEmail}
          onChange={(e) => { setNewEmail(e.target.value); setEmailError(""); setError(""); }}
          placeholder="new@example.com"
          autoComplete="email"
          required
          disabled={saving}
          error={emailError}
        />

        <AlertBanner
          message="Supabase will send a confirmation link to both addresses. The change only takes effect after you click both links."
          variant="info"
        />

        <button
          type="submit"
          disabled={saving}
          className="self-start flex items-center gap-2 px-5 py-2.5
                     bg-accent hover:bg-accent-dark text-primary-dark font-bold text-sm
                     rounded-xl shadow-md shadow-yellow-500/20
                     transition-all duration-150 active:scale-95
                     disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving && <Loader2 size={15} className="animate-spin" />}
          Send Confirmation
        </button>
      </form>
    </SettingsCard>
  );
}

/* ─── Main page ─── */

export default function AccountPage() {
  const { user } = useAuth();
  const { profile, profileLoading, profileError, updateFullName, uploadAvatar } = useProfile();

  return (
    <AccountLayout>
      <ProfileOverviewSection
        user={user}
        profile={profile}
        profileLoading={profileLoading}
      />

      <ProfileDetailsSection
        profile={profile}
        profileLoading={profileLoading}
        profileError={profileError}
        updateFullName={updateFullName}
        uploadAvatar={uploadAvatar}
      />

      <ChangePasswordSection user={user} />

      <ChangeEmailSection user={user} />
    </AccountLayout>
  );
}
