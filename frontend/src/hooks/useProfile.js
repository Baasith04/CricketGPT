/**
 * useProfile.js
 * Custom hook that reads and writes the authenticated user's row in public.profiles.
 *
 * The public.profiles table is expected to have:
 *   id          uuid  (references auth.users)
 *   full_name   text
 *   avatar_url  text  (nullable)
 *   created_at  timestamptz
 *
 * Row Level Security on public.profiles must allow:
 *   SELECT  WHERE id = auth.uid()
 *   UPDATE  WHERE id = auth.uid()
 */

import { useState, useEffect, useCallback } from "react";
import { supabase } from "../services/supabase";
import { useAuth } from "../context/AuthContext";

export function useProfile() {
  const { user } = useAuth();

  const [profile, setProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileError, setProfileError] = useState(null);

  /** Fetch the profile row for the signed-in user. */
  const fetchProfile = useCallback(async () => {
    if (!user?.id) {
      setProfile(null);
      setProfileLoading(false);
      return;
    }

    setProfileLoading(true);
    setProfileError(null);

    try {
      const { data, error } = await supabase
        .from("profiles")
        .select("id, full_name, avatar_url, created_at")
        .eq("id", user.id)
        .single();

      if (error) throw error;
      setProfile(data);
    } catch (err) {
      setProfileError(err?.message ?? "Failed to load profile.");
      setProfile(null);
    } finally {
      setProfileLoading(false);
    }
  }, [user?.id]);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  /**
   * Update full_name in public.profiles AND sync auth user_metadata.
   * Never touches another user's row — the WHERE clause is enforced both
   * client-side (eq("id", user.id)) and by Supabase RLS.
   */
  const updateFullName = useCallback(
    async (fullName) => {
      if (!user?.id) throw new Error("Not authenticated.");

      const trimmed = fullName.trim();
      if (!trimmed) throw new Error("Name cannot be empty.");
      if (trimmed.length < 2) throw new Error("Name must be at least 2 characters.");

      // 1. Update public.profiles
      const { error: profileErr } = await supabase
        .from("profiles")
        .update({ full_name: trimmed })
        .eq("id", user.id);

      if (profileErr) throw profileErr;

      // 2. Keep auth user_metadata in sync
      const { error: authErr } = await supabase.auth.updateUser({
        data: { full_name: trimmed },
      });

      if (authErr) throw authErr;

      // 3. Reflect locally without a round-trip
      setProfile((prev) => (prev ? { ...prev, full_name: trimmed } : prev));
    },
    [user?.id]
  );

  /**
   * Upload a new avatar to Supabase Storage bucket "avatars".
   * Returns the public URL on success, throws on failure.
   * If the bucket does not exist, throws a descriptive error.
   */
  const uploadAvatar = useCallback(
    async (file) => {
      if (!user?.id) throw new Error("Not authenticated.");

      const ext = file.name.split(".").pop().toLowerCase();
      const allowed = ["jpg", "jpeg", "png", "webp", "gif"];
      if (!allowed.includes(ext)) throw new Error("Only JPG, PNG, WebP and GIF images are allowed.");
      if (file.size > 2 * 1024 * 1024) throw new Error("Image must be smaller than 2 MB.");

      const path = `${user.id}/avatar.${ext}`;

      const { error: uploadErr } = await supabase.storage
        .from("avatars")
        .upload(path, file, { upsert: true, contentType: file.type });

      if (uploadErr) {
        if (uploadErr.message?.includes("Bucket not found") || uploadErr.statusCode === 404) {
          throw new Error(
            "Avatar upload is not configured yet. The 'avatars' Storage bucket needs to be created in the Supabase dashboard."
          );
        }
        throw uploadErr;
      }

      const { data: urlData } = supabase.storage.from("avatars").getPublicUrl(path);
      const publicUrl = `${urlData.publicUrl}?t=${Date.now()}`;

      // Store URL in profiles
      const { error: profileErr } = await supabase
        .from("profiles")
        .update({ avatar_url: publicUrl })
        .eq("id", user.id);

      if (profileErr) throw profileErr;

      setProfile((prev) => (prev ? { ...prev, avatar_url: publicUrl } : prev));
      return publicUrl;
    },
    [user?.id]
  );

  return {
    profile,
    profileLoading,
    profileError,
    fetchProfile,
    updateFullName,
    uploadAvatar,
  };
}
