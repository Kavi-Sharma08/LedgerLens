import "server-only";

import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import Google from "next-auth/providers/google";
import { MongoDBAdapter } from "@auth/mongodb-adapter";

import clientPromise, { getAuthDatabase } from "@/lib/mongo";
import { verifyUserCredentials } from "@/lib/registration";

/**
 * Auth.js is the single authentication authority for LedgerLens.
 *
 * - Google OAuth handshake: handled here (callback lives at
 *   /api/auth/callback/google — FastAPI must never own an OAuth callback).
 * - Email + password: Credentials provider validating against MongoDB with
 *   bcrypt; hashes are only ever compared here.
 * - Sessions: JWT strategy (required by the Credentials provider), delivered
 *   as an encrypted HttpOnly cookie signed with AUTH_SECRET.
 * - Users/accounts: persisted through the MongoDB adapter so Google accounts
 *   link consistently and business data can reference stable user ids.
 *
 * FastAPI never sees AUTH_SECRET or OAuth secrets: authenticated API calls are
 * forwarded by src/app/api/backend/[...path] which injects trusted identity
 * headers after Auth.js has validated the session (see docs/authentication.md).
 */

if (!process.env.AUTH_SECRET) {
  throw new Error("AUTH_SECRET is not set. Add it to client/.env.local.");
}

const SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 7; // 7 days

export const authConfig = {
  trustHost: true,
  secret: process.env.AUTH_SECRET,
  adapter: MongoDBAdapter(clientPromise, {
    databaseName: process.env.MONGODB_DATABASE || "ledgerlens",
  }),
  session: { strategy: "jwt", maxAge: SESSION_MAX_AGE_SECONDS },
  pages: {
    signIn: "/login",
    error: "/login", // OAuth failures land on /login?error=<code>
  },
  providers: [
    Google({
      clientId: process.env.AUTH_GOOGLE_ID,
      clientSecret: process.env.AUTH_GOOGLE_SECRET,
      // Secure default: a Google account whose email matches an existing
      // password account requires an explicit in-app link (later phase),
      // preventing silent account takeover via unverified external emails.
      allowDangerousEmailAccountLinking: false,
    }),
    Credentials({
      credentials: {
        email: {},
        password: {},
      },
      async authorize(credentials) {
        const email = String(credentials?.email ?? "").trim().toLowerCase();
        const password = String(credentials?.password ?? "");
        if (!email || !password) return null;

        try {
          return await verifyUserCredentials(email, password);
        } catch (error) {
          // Network/database problems fail closed instead of logging anyone in.
          console.error("[auth] credential validation failed:", error);
          return null;
        }
      },
    }),
  ],
  callbacks: {
    // The default token already carries sub = user.id; surface it on the session.
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.sub;
      }
      return session;
    },
  },
  events: {
    // First-ever Google sign-in creates the adapter user row.
    // We do NOT auto-create a workspace here — the onboarding flow
    // handles workspace creation for new users.
  },
};

export const { handlers, auth, signIn, signOut } = NextAuth(authConfig);

export { getAuthDatabase };
