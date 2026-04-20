import { ChatWindow } from "./components/chat/ChatWindow";
import { Layout } from "./components/layout/Layout";
import { useFoundryAuth } from "./hooks/useFoundryAuth";

export default function App() {
  const { state, signIn } = useFoundryAuth();

  if (state.status === "loading") {
    return (
      <div className="flex h-full items-center justify-center text-gray-500 text-sm">
        Loading…
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-sm">
        <p className="text-red-400">Authentication error: {state.message}</p>
        <button
          onClick={signIn}
          className="rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-500"
        >
          Try again
        </button>
      </div>
    );
  }

  if (state.status === "unauthenticated") {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-white">Lobster</h1>
          <p className="mt-1 text-sm text-gray-500">OpenClaw on Palantir Foundry</p>
        </div>
        <button
          onClick={signIn}
          className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-blue-500"
        >
          Sign in with Foundry
        </button>
      </div>
    );
  }

  return (
    <Layout>
      <ChatWindow token={state.token} />
    </Layout>
  );
}
