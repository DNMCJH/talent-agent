import NextAuth from "next-auth";
import GitHub from "next-auth/providers/github";

const API_BASE = process.env.INTERNAL_API_BASE ?? process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    GitHub({
      clientId: process.env.AUTH_GITHUB_ID,
      clientSecret: process.env.AUTH_GITHUB_SECRET,
      // public_repo only — the app reads repo metadata for matching and never
      // needs write access or private-repo contents. Avoids handing the browser
      // a token with full private read/write scope.
      authorization: { params: { scope: "read:user user:email public_repo" } },
    }),
  ],
  callbacks: {
    async jwt({ token, account }) {
      if (account?.access_token) {
        token.githubAccessToken = account.access_token;
        // The backend JWT is required for every API call. If this exchange
        // fails, fail the sign-in outright — otherwise the user appears logged
        // in but every request 401s until they sign in again.
        let res: Response;
        try {
          res = await fetch(`${API_BASE}/auth/github-token`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ access_token: account.access_token }),
          });
        } catch {
          throw new Error("Backend unreachable during sign-in");
        }
        if (!res.ok) {
          throw new Error(`Backend rejected GitHub sign-in (${res.status})`);
        }
        const data = await res.json();
        token.backendJwt = data.access_token;
        token.userId = data.user_id;
        token.githubLogin = data.github_login;
      }
      return token;
    },
    async session({ session, token }) {
      const t = token as Record<string, unknown>;
      const s = session as unknown as {
        backendJwt?: string;
        userId?: number;
        githubLogin?: string;
        githubAccessToken?: string;
        user?: unknown;
        expires: string;
      };
      s.backendJwt = t.backendJwt as string | undefined;
      s.userId = t.userId as number | undefined;
      s.githubLogin = t.githubLogin as string | undefined;
      s.githubAccessToken = t.githubAccessToken as string | undefined;
      return s as typeof session;
    },
  },
  pages: {
    signIn: "/login",
  },
});
