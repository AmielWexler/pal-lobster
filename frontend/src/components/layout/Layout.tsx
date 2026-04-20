import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
}

export function Layout({ children }: Props) {
  return (
    <div className="flex h-full flex-col bg-gray-950">
      <header className="flex items-center gap-3 border-b border-gray-800 px-4 py-3">
        <span className="text-lg font-semibold text-white">Lobster</span>
        <span className="rounded bg-gray-800 px-2 py-0.5 text-xs text-gray-400">
          OpenClaw on Foundry
        </span>
      </header>
      <main className="flex min-h-0 flex-1 flex-col">{children}</main>
    </div>
  );
}
