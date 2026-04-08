"use client";

import { useEffect, useMemo, useState } from "react";

import { marketingPlatforms } from "@/lib/marketing";

const DEMO_DEFAULTS = ["youtube", "instagram", "naver-blog", "line", "threads", "linkedin"];

export function InteractiveDemo() {
  const [topic, setTopic] = useState("Launch week video breakdown");
  const [selected, setSelected] = useState<string[]>(DEMO_DEFAULTS);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (!running) return;

    const timer = window.setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          window.clearInterval(timer);
          return 100;
        }
        return prev + 5;
      });
    }, 110);

    return () => window.clearInterval(timer);
  }, [running]);

  useEffect(() => {
    if (progress >= 100) {
      const doneTimer = window.setTimeout(() => {
        setRunning(false);
      }, 1000);

      return () => window.clearTimeout(doneTimer);
    }
  }, [progress]);

  function togglePlatform(id: string) {
    setSelected((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  function handleGenerate() {
    setRunning(true);
    setProgress(0);
  }

  const activePlatforms = marketingPlatforms.filter((platform) => selected.includes(platform.id));

  const codeSnippet = useMemo(
    () =>
      `await client.bombs.create({\n  topic: "${topic || "Launch week video breakdown"}",\n  platforms: [${activePlatforms.map((platform) => `"${platform.id.replace("-", "_")}"`).join(", ")}],\n  replyPolicy: "autopilot",\n  locale: "ko-KR"\n})`,
    [activePlatforms, topic]
  );

  return (
    <section className="section">
      <div className="section-heading">
        <span className="eyebrow">Interactive demo</span>
        <h2>Watch the burst happen before you sign up.</h2>
        <p>It is mock data, but the interaction is the point: one brief in, many endpoints out, and code that stays ridiculously short.</p>
      </div>

      <div className="interactive-demo">
        <div className="interactive-demo__builder">
          <div className="interactive-demo__panel">
            <label className="interactive-demo__label" htmlFor="demo-topic">
              1. Enter a topic
            </label>
            <input
              id="demo-topic"
              className="interactive-demo__input"
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
              placeholder="Type the launch topic"
            />
          </div>

          <div className="interactive-demo__panel">
            <div className="interactive-demo__label">2. Choose platforms</div>
            <div className="interactive-demo__platforms">
              {marketingPlatforms.map((platform) => {
                const active = selected.includes(platform.id);
                return (
                  <button
                    key={platform.id}
                    type="button"
                    className={`interactive-demo__platform${active ? " is-active" : ""}`}
                    onClick={() => togglePlatform(platform.id)}
                  >
                    <span className="interactive-demo__platform-glyph" style={{ color: platform.color }}>
                      {platform.short}
                    </span>
                    <span>{platform.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="interactive-demo__actions">
            <button type="button" className="button button--primary button--xl" onClick={handleGenerate} disabled={selected.length === 0 || running}>
              {running ? "Generating..." : "Generate burst"}
            </button>
            <p>3. Then ship it for real once the burst looks right.</p>
          </div>
        </div>

        <div className="interactive-demo__results">
          <div className="interactive-demo__status-card">
            <div className="interactive-demo__status-header">
              <span className="eyebrow eyebrow--compact">Burst status</span>
              <strong>{running ? "Generating + distributing" : progress >= 100 ? "Burst complete" : "Ready to launch"}</strong>
            </div>

            <div className="interactive-demo__progress">
              <div className="interactive-demo__progress-bar" style={{ width: `${progress}%` }} />
            </div>

            <div className="interactive-demo__result-grid">
              {activePlatforms.map((platform, index) => {
                const threshold = Math.min(100, (index + 1) * (100 / Math.max(activePlatforms.length, 1)));
                const complete = progress >= threshold;

                return (
                  <div key={platform.id} className={`interactive-demo__result${complete ? " is-complete" : ""}`}>
                    <span className="interactive-demo__result-glyph" style={{ color: platform.color }}>
                      {complete ? "✓" : platform.short}
                    </span>
                    <div>
                      <strong>{platform.label}</strong>
                      <span>{complete ? "published" : running ? "routing" : "queued"}</span>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="interactive-demo__cta">
              <strong>Sign up to do this for real.</strong>
              <p>Real publish jobs, real comments, real platform adapters.</p>
              <a className="button button--ghost" href="#pricing">
                Start free
              </a>
            </div>
          </div>

          <div className="interactive-demo__code-card">
            <div className="interactive-demo__status-header">
              <span className="eyebrow eyebrow--compact">API call</span>
              <strong>One request</strong>
            </div>
            <pre className="interactive-demo__code">
              <code>{codeSnippet}</code>
            </pre>
          </div>
        </div>
      </div>
    </section>
  );
}
