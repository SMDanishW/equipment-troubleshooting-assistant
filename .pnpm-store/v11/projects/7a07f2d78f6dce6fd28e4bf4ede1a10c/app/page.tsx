import Link from "next/link";

export default function HomePage() {
  return (
    <main className="page-shell">
      <section className="panel">
        <h1>Equipment Troubleshooting Agent</h1>
        <p>
          Local-first portfolio build for authenticated manual upload, multimodal RAG, agent traces, and streaming
          troubleshooting answers.
        </p>
        <div className="actions">
          <Link className="button primary" href="/documents">
            Documents
          </Link>
          <Link className="button" href="/chat">
            Chat
          </Link>
        </div>
      </section>
    </main>
  );
}
