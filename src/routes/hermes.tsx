import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/hermes")({ component: HermesPage });

const CLI = `./run-desktop.sh

# or, photos in / videos out from a folder:
export PYTHONPATH=src
python3 -m photomotion auth --login
python3 -m photomotion run \\
  --input ./data/INBOX/wanatah \\
  --job-dir ./data/jobs/wanatah \\
  --address "405 N Main St" \\
  --city "Wanatah, IN 46390" \\
  --dry-run --music wallpaper`;

function HermesPage() {
  return (
    <AppShell current="hermes">
      <main className="mx-auto min-w-0 max-w-3xl overflow-x-hidden px-4 py-8 sm:px-6 sm:py-10">
        <p className="label-kicker">Standalone · Hermes</p>
        <h1 className="mt-2 font-display text-3xl tracking-tight sm:text-4xl">
          Desktop photos in, videos out
        </h1>
        <p className="mt-3 max-w-xl text-sm text-muted">
          Unzip the kit on a Mac, Linux box, or Windows PC with Python 3.10+ and
          ffmpeg. Drop stills. This machine writes 1080p MP4s. Ken Burns is
          offline. Imagine is opt-in via your X account at console.x.ai.
        </p>

        <section className="panel mt-8">
          <h2 className="text-lg font-semibold">Download the desktop kit</h2>
          <p className="mt-1 text-sm text-muted">
            Code, music beds, tests, and a one-command launcher. No listing
            photos. Unzip, install numpy + pillow, double-click run-desktop.
          </p>
          <div className="mt-4 flex min-w-0 flex-wrap gap-2">
            <Button asChild size="sm">
              <a href="/downloads/photomotion-desktop.zip" download>
                Download photomotion-desktop.zip
              </a>
            </Button>
            <Button asChild size="sm" variant="secondary">
              <a href="https://github.com/dain12344321/photomotion" target="_blank" rel="noreferrer">
                GitHub
              </a>
            </Button>
          </div>
        </section>

        <section className="panel mt-5">
          <h2 className="text-lg font-semibold">X account authorization</h2>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-muted">
            <li>Sign in with X on this desk if you want operator identity here.</li>
            <li>
              On the desktop kit, run{" "}
              <code className="font-mono text-fg">python3 -m photomotion auth --login</code>
            </li>
            <li>That opens console.x.ai. Sign in with the same X account and create a key.</li>
            <li>Paste the key at the hidden prompt. It is stored at ~/.photomotion/credentials.json (mode 600) and never printed.</li>
            <li>
              Live Imagine: add{" "}
              <code className="font-mono text-fg">
                --live --confirm-live --spend-cap 15 --i2v-heroes 2
              </code>
            </li>
          </ol>
          <p className="mt-3 text-xs text-subtle">
            Ken Burns does not need a key. Dry-run is the default and writes the
            same 16:9 / 9:16 / 1:1 masters with Ken Burns only.
          </p>
        </section>

        <section className="panel mt-5">
          <h2 className="text-lg font-semibold">Run a property</h2>
          <pre className="mt-3 max-w-full overflow-x-auto rounded-[var(--radius-sm)] bg-ink p-4 font-mono text-xs text-fg">
            {CLI}
          </pre>
          <p className="mt-3 text-sm text-muted">
            <code className="font-mono text-fg">./run-desktop.sh</code> (or{" "}
            <code className="font-mono text-fg">run-desktop.bat</code>) starts the
            local drop desk. ffmpeg writes DELIVER mp4s on that machine.
          </p>
        </section>

        <section className="panel mt-5">
          <h2 className="text-lg font-semibold">Git + Cloudflare</h2>
          <p className="mt-2 text-sm text-muted">
            Clone the GitHub repo for the operator desk. Camera, beats, and tour
            planning run in the browser, so Cloudflare Pages can host the UI.
            Python + ffmpeg stay on the desktop — Workers cannot encode Lanczos
            1080p.
          </p>
        </section>
      </main>
    </AppShell>
  );
}
