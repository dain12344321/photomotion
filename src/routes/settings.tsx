import { useEffect, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { xaiStatus } from "@/lib/xai.functions";
import { SignedIn, SignedOut } from "@/lib/auth/gates";

export const Route = createFileRoute("/settings")({
  loader: () => xaiStatus(),
  component: SettingsPage,
});

function SettingsPage() {
  const status = Route.useLoaderData();
  const [cap, setCap] = useState(15);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("photomotion.settings");
      if (raw) {
        const parsed = JSON.parse(raw) as { cap?: number };
        if (parsed.cap) setCap(parsed.cap);
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    localStorage.setItem("photomotion.settings", JSON.stringify({ cap }));
  }, [cap]);

  return (
    <AppShell current="settings">
      <main className="mx-auto max-w-2xl px-4 py-8 sm:px-6 sm:py-10">
        <p className="label-kicker">Lakeshore Listing Media</p>
        <h1 className="mt-2 font-display text-3xl tracking-tight">Settings</h1>
        <p className="mt-2 text-sm text-muted">
          Ken Burns is always free and offline. Imagine spends your xAI quota and
          is signed-in + confirm only.
        </p>

        <section className="panel mt-8">
          <h2 className="text-sm font-semibold">X account</h2>
          <p className="mt-2 text-sm text-muted">
            Sign in with X on this desk to mark yourself as the operator. Desktop
            Imagine uses the API key from console.x.ai (same X login).
          </p>
          <div className="mt-4 text-sm">
            <SignedIn>
              <p className="text-ok">X session connected for this desk.</p>
            </SignedIn>
            <SignedOut>
              <Link to="/login" className="text-lake no-underline hover:underline">
                Sign in with X
              </Link>
            </SignedOut>
          </div>
        </section>

        <section className="panel mt-5">
          <h2 className="text-sm font-semibold">xAI · Imagine</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-muted">Server key</dt>
              <dd className="font-mono text-fg">{status.configured ? "Present" : "Not injected"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted">Video model</dt>
              <dd className="font-mono text-fg">{status.model}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted">Default lane</dt>
              <dd className="text-fg">Ken Burns · $0</dd>
            </div>
          </dl>
        </section>

        <section className="panel mt-5">
          <h2 className="text-sm font-semibold">Spend cap</h2>
          <p className="mt-1 text-xs text-subtle">
            Hard cap $25. Each 4s 1080p clip is about $1.01. $15 covers a full
            push-in hero pass.
          </p>
          <input
            type="range"
            min={0}
            max={25}
            step={1}
            value={cap}
            onChange={(e) => setCap(Number(e.target.value))}
            className="mt-4 w-full"
          />
          <p className="mt-2 font-mono text-sm tabular-nums">${cap.toFixed(0)}</p>
        </section>

        <section className="panel mt-5">
          <h2 className="text-sm font-semibold">Motion law</h2>
          <ul className="mt-3 space-y-2 text-sm text-muted">
            <li>Automatic: push-in, orbit, pull-out, Ken Burns, static.</li>
            <li>Banned: pan, I2V orbit, I2V pull-out.</li>
            <li>Baths, laundry, garage, mirrors stay static.</li>
            <li>Trapezoid speed ramp. Soft dissolve inside the holds.</li>
            <li>Cuts snap to 4-beat bars. Dual-band onset lock.</li>
          </ul>
        </section>
      </main>
    </AppShell>
  );
}
