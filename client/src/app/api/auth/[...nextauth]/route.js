import { handlers } from "@/lib/auth";

/**
 * Auth.js route handlers. Owns every authentication endpoint:
 *   /api/auth/signin/*  /api/auth/callback/*  /api/auth/signout
 *   /api/auth/session   /api/auth/csrf        /api/auth/providers
 *
 * The Google OAuth callback is therefore http://localhost:3000/api/auth/callback/google.
 */
export const { GET, POST } = handlers;
