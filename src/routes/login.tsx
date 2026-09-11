import { createFileRoute, Link, Navigate } from "@tanstack/react-router";
import { GROK_PROVIDERS, authEnabled, signIn } from "@/lib/auth/client";
import { useCurrentUserState } from "@/lib/auth/use-current-user";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/login")({ component: Login });

function Login() {
  const { user, isPending } = useCurrentUserState();
  const providers = [...GROK_PROVIDERS].sort((a, b) =>
    a.idp === "twitter" ? -1 : b.idp === "twitter" ? 1 : 0,
  );

  if (isPending) {
    return (
      <main className="relative grid min-h-dvh place-items-center overflow-hidden bg-bg px-6">
        <LoginStill />
        <div className="relative w-full max-w-sm">
          <div className="h-3 w-40 animate-pulse rounded bg-elevated" />
          <div className="mt-3 h-9 w-56 animate-pulse rounded bg-elevated" />
          <div className="mt-8 h-11 w-full animate-pulse rounded-full bg-elevated" />
          <div className="mt-3 h-11 w-full animate-pulse rounded-full bg-elevated" />
        </div>
      </main>
    );
  }

  if (user) {
    return <Navigate to="/" />;
  }

  return (
    <main className="relative grid min-h-dvh place-items-center overflow-hidden bg-bg px-6">
      <LoginStill />
      <div className="relative w-full max-w-sm">
        <p className="label-kicker">Lakeshore Listing Media</p>
        <h1 className="mt-3 font-display text-4xl tracking-tight">PhotoMotion</h1>
        <p className="mt-2 text-sm text-muted">
          Sign in with X to authorize Imagine heroes on your listing stills. Ken
          Burns tours run offline either way.
        </p>
        <div className="mt-8 space-y-3">
          {authEnabled ? (
            providers.map((p) => (
              <Button
                key={p.providerId}
                type="button"
                variant={p.idp === "twitter" ? "primary" : "secondary"}
                className="w-full"
                onClick={() => signIn(p.providerId, { callbackURL: "/" })}
              >
                Continue with {p.label}
              </Button>
            ))
          ) : (
            <p className="text-sm text-muted">Sign-in is disabled in this build.</p>
          )}
        </div>
        <Link to="/" className="mt-8 inline-block text-sm font-medium text-lake no-underline hover:underline">
          Back to the desk — Ken Burns does not need an account
        </Link>
      </div>
    </main>
  );
}

function LoginStill() {
  return (
    <>
      <img
        src="/listings/wanatah/001.jpg"
        alt=""
        className="pointer-events-none absolute inset-0 h-full w-full object-cover opacity-40"
      />
      <div className="pointer-events-none absolute inset-0 bg-bg/80" />
    </>
  );
}
