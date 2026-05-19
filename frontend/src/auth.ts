import NextAuth from "next-auth";
import GitHub from "next-auth/providers/github";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    GitHub({
      clientId: process.env.AUTH_GITHUB_ID,
      clientSecret: process.env.AUTH_GITHUB_SECRET,
      authorization: { params: { scope: "read:user user:email repo" } },
    }),
  ],
  callbacks: {
    async jwt({ token, account }) {
      if (account?.access_token) {
        token.githubAccessToken = account.access_token;
        try {
          const res = await fetch(`${API_BASE}/auth/github-token`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ access_token: account.access_token }),
          });
          if (res.ok) {
            const data = await res.json();
            token.backendJwt = data.access_token;
            token.userId = data.user_id;
            token.githubLogin = data.github_login;
          }
        } catch {
          // network error
        }
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
