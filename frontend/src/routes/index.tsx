import { createFileRoute } from "@tanstack/react-router";
import { App } from "@/components/App";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "My Movie Tracker" },
      { name: "description", content: "Discover, track, and quiz yourself on movies inside Telegram." },
      { property: "og:title", content: "My Movie Tracker" },
      { property: "og:description", content: "A premium Telegram Web App to track and discover movies." },
    ],
  }),
  component: Index,
});

function Index() {
  return <App />;
}
