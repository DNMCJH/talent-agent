import { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session extends DefaultSession {
    backendJwt?: string;
    userId?: number;
    githubLogin?: string;
    githubAccessToken?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    backendJwt?: string;
    userId?: number;
    githubLogin?: string;
    githubAccessToken?: string;
  }
}

export {};
