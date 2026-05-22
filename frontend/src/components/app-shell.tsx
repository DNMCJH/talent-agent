import { Nav } from "@/components/nav";
import { EmailVerifyBanner } from "@/components/email-verify-banner";
import { CursorDots } from "@/components/cursor-dots";

/** App chrome — nav + verify banner + centered content column. Shared by the
 *  (app) route group layout and the authenticated root homepage. */
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative min-h-screen flex flex-col">
      <CursorDots />
      <Nav />
      <EmailVerifyBanner />
      <main className="relative z-[1] flex-1 container max-w-7xl mx-auto px-4 sm:px-6 py-6">
        {children}
      </main>
    </div>
  );
}
