import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { UserButton, SignedIn, SignedOut } from "@/lib/auth/gates";
import { useCurrentUserState } from "@/lib/auth/use-current-user";
import { cn } from "@/lib/utils";

export function AppShell({
  children,
  current,
}: {
  children: ReactNode;
  current?: "work" | "hermes" | "settings";
}) {
  const { isPending } = useCurrentUserState();

  return (
    <div className="flex min-h-dvh flex-col overflow-x-hidden bg-bg text-fg">
      <header className="sticky top-0 z-30 border-b border-border bg-surface/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[88rem] items-center justify-between gap-2 px-3 sm:h-[4.25rem] sm:gap-4 sm:px-6">
          <Link to="/" className="flex min-w-0 items-center gap-3 no-underline">
            <img
              src="/brand/logo-light-sm.png"
              alt="Lakeshore Listing Media"
              className="h-8 w-auto sm:h-9"
            />
            <span className="hidden h-5 w-px bg-border sm:block" />
            <span className="hidden font-display text-sm tracking-tight text-fg sm:block">
              PhotoMotion
            </span>
          </Link>
          <nav className="flex min-w-0 items-center gap-0.5 sm:gap-1">
            <NavLink to="/" active={current === "work"}>
              Desk
            </NavLink>
            <NavLink to="/hermes" active={current === "hermes"}>
              <span className="sm:hidden">Kit</span>
              <span className="hidden sm:inline">Desktop</span>
            </NavLink>
            <NavLink to="/settings" active={current === "settings"}>
              Settings
            </NavLink>
            <span className="ml-1 hidden h-5 w-px bg-border sm:ml-2 sm:block" />
            <div className="ml-1 min-w-0 max-w-[7.5rem] overflow-hidden sm:max-w-none">
              {isPending ? (
                <div className="h-8 w-16 animate-pulse rounded-full bg-elevated sm:w-24" />
              ) : (
                <>
                  <SignedIn>
                    <UserButton />
                  </SignedIn>
                  <SignedOut>
                    <Link
                      to="/login"
                      className="inline-flex min-h-9 items-center rounded-full px-3 py-2 text-xs font-semibold uppercase tracking-wider text-lake no-underline hover:text-fg sm:px-4"
                    >
                      <span className="sm:hidden">Sign in</span>
                      <span className="hidden sm:inline">Sign in with X</span>
                    </Link>
                  </SignedOut>
                </>
              )}
            </div>
          </nav>
        </div>
      </header>
      <div className="flex-1">{children}</div>
      <footer className="mt-auto border-t border-border bg-surface">
        <div className="mx-auto flex max-w-[88rem] flex-wrap items-center justify-between gap-2 px-4 py-4 sm:px-6">
          <p className="text-xs text-subtle">PhotoMotion™ · stills stay the authority</p>
          <p className="text-xs text-subtle">Offline Ken Burns · optional Imagine</p>
        </div>
      </footer>
    </div>
  );
}

function NavLink({
  to,
  active,
  children,
}: {
  to: "/" | "/hermes" | "/settings";
  active?: boolean;
  children: ReactNode;
}) {
  return (
    <Link
      to={to}
      className={cn(
        "rounded-full px-2 py-2 text-[11px] font-semibold uppercase tracking-wider no-underline transition-colors duration-[var(--motion-quick)] sm:px-4 sm:text-xs",
        active ? "text-fg" : "text-muted hover:text-fg",
      )}
    >
      {children}
    </Link>
  );
}
