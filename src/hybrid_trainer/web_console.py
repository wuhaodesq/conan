from __future__ import annotations

from html import escape
from pathlib import Path

from .decision_console import DecisionConsole


def render_decision_console_html(console: DecisionConsole) -> str:
    data = console.to_dict()
    metrics = data["dashboard"]["metrics"]
    failures = data["dashboard"]["failures"]
    review_queue = data["review_queue"]
    strategy = data["strategy"]
    curriculum = data["curriculum"]
    policy = data["policy"]
    active_learning = data["active_learning"]

    cards = [
        _metric_card("Approve", metrics["approve"], "Stable policy candidates"),
        _metric_card("Review", metrics["review"], "Needs human calibration"),
        _metric_card("Block", metrics["block"], "Needs corrective action"),
        _metric_card("Pending Queue", review_queue["pending_count"], "Human review backlog"),
    ]

    recommendation_items = "".join(
        f"<li><strong>{escape(item['node'])}</strong><span>{escape(item['reason'])}</span></li>"
        for item in data["major_node_recommendations"]
    ) or "<li><strong>none</strong><span>No major node recommendations yet.</span></li>"

    review_items = "".join(
        (
            "<tr>"
            f"<td>{item['iteration']}</td>"
            f"<td>{escape(item['node'])}</td>"
            f"<td>{item['auto_score']:.2f}</td>"
            f"<td>{escape(item['auto_decision'])}</td>"
            f"<td>{item['risk_score']:.2f}</td>"
            "</tr>"
        )
        for item in review_queue["prioritized_items"]
    ) or '<tr><td colspan="5">No pending review items.</td></tr>'

    active_learning_items = "".join(
        (
            "<tr>"
            f"<td>{item['iteration']}</td>"
            f"<td>{item['score']:.2f}</td>"
            f"<td>{item['uncertainty']:.2f}</td>"
            "</tr>"
        )
        for item in active_learning["candidates"]
    ) or '<tr><td colspan="3">No active learning candidates.</td></tr>'

    event_items = "".join(
        f"<li><span>{escape(item['timestamp'])}</span><strong>{escape(item['event_type'])}</strong></li>"
        for item in data["recent_events"]
    ) or "<li><span>No recent events.</span><strong>idle</strong></li>"

    policy_items = "".join(
        (
            "<li>"
            f"<strong>{escape(item['version'])}</strong>"
            f"<span>{escape(item['note'] or 'no note')}</span>"
            f"<em>{'active' if item['is_active'] else 'inactive'}</em>"
            "</li>"
        )
        for item in policy["available_versions"]
    ) or "<li><strong>none</strong><span>No registered policies.</span><em>inactive</em></li>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hybrid Trainer Visual Console</title>
  <style>
    :root {{
      --bg: #f4efe7;
      --panel: rgba(255, 252, 247, 0.88);
      --ink: #21302b;
      --muted: #60716c;
      --accent: #b1532d;
      --accent-soft: #f1c7b6;
      --line: rgba(33, 48, 43, 0.12);
      --shadow: 0 24px 60px rgba(71, 54, 34, 0.12);
      --radius: 22px;
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(255, 212, 180, 0.7), transparent 32%),
        radial-gradient(circle at top right, rgba(171, 210, 193, 0.75), transparent 28%),
        linear-gradient(135deg, #f6f1e8 0%, #eef2e8 100%);
      font-family: "Trebuchet MS", Verdana, sans-serif;
    }}
    .shell {{
      max-width: 1240px;
      margin: 0 auto;
      padding: 40px 20px 56px;
    }}
    .hero {{
      padding: 28px 30px;
      border-radius: calc(var(--radius) + 6px);
      background: linear-gradient(145deg, rgba(255,255,255,0.86), rgba(247, 236, 224, 0.94));
      box-shadow: var(--shadow);
      border: 1px solid rgba(255,255,255,0.65);
    }}
    .eyebrow {{
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--accent);
      font-size: 12px;
      margin-bottom: 12px;
    }}
    h1, h2 {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      font-weight: 700;
    }}
    h1 {{
      font-size: clamp(2rem, 4vw, 3.5rem);
      line-height: 1.03;
    }}
    .hero p {{
      margin: 14px 0 0;
      max-width: 760px;
      color: var(--muted);
      font-size: 1rem;
      line-height: 1.7;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: 18px;
      margin-top: 22px;
    }}
    .card {{
      background: var(--panel);
      backdrop-filter: blur(14px);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 22px;
    }}
    .metric-card {{
      grid-column: span 3;
    }}
    .metric-card strong {{
      display: block;
      font-size: 2rem;
      margin: 8px 0 6px;
    }}
    .metric-card span {{
      color: var(--muted);
      font-size: 0.95rem;
    }}
    .half {{
      grid-column: span 6;
    }}
    .full {{
      grid-column: span 12;
    }}
    .stack {{
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 14px;
    }}
    .meta-grid div {{
      padding: 14px;
      border-radius: 16px;
      background: rgba(255,255,255,0.55);
      border: 1px solid var(--line);
    }}
    .meta-grid strong {{
      display: block;
      margin-top: 6px;
      font-size: 1.05rem;
    }}
    ul.clean {{
      list-style: none;
      padding: 0;
      margin: 16px 0 0;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    ul.clean li {{
      display: flex;
      justify-content: space-between;
      gap: 14px;
      padding: 14px 16px;
      border-radius: 16px;
      background: rgba(255,255,255,0.58);
      border: 1px solid var(--line);
      align-items: baseline;
    }}
    ul.clean li strong {{
      font-size: 0.96rem;
    }}
    ul.clean li span {{
      flex: 1;
      color: var(--muted);
      font-size: 0.92rem;
      line-height: 1.5;
    }}
    ul.clean li em {{
      color: var(--accent);
      font-style: normal;
      font-size: 0.85rem;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 16px;
    }}
    th, td {{
      padding: 12px 10px;
      text-align: left;
      border-bottom: 1px solid var(--line);
      font-size: 0.94rem;
    }}
    th {{
      color: var(--muted);
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 0.75rem;
    }}
    .subtle {{
      color: var(--muted);
      font-size: 0.94rem;
      line-height: 1.6;
      margin-top: 10px;
    }}
    @media (max-width: 960px) {{
      .metric-card,
      .half {{
        grid-column: span 12;
      }}
      .meta-grid {{
        grid-template-columns: 1fr;
      }}
      ul.clean li {{
        flex-direction: column;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="eyebrow">Hybrid Self-Improvement Trainer</div>
      <h1>Visual Decision Console</h1>
      <p>
        A shareable operator view for metrics, review pressure, strategy readiness, and recent system signals.
        This HTML artifact is generated from the same decision console data used by the CLI and JSON exports.
      </p>
      <div class="meta-grid">
        <div><span>Current Strategy</span><strong>{escape(strategy['current'])}</strong></div>
        <div><span>Recommended Strategy</span><strong>{escape(strategy['recommended'])}</strong></div>
        <div><span>Policy Version</span><strong>{escape(policy['active_version'] or '-')}</strong></div>
      </div>
    </section>

    <section class="grid">
      {''.join(cards)}

      <article class="card half">
        <h2>Major Node Recommendations</h2>
        <p class="subtle">The highest leverage human intervention points inferred from current run signals.</p>
        <ul class="clean">{recommendation_items}</ul>
      </article>

      <article class="card half">
        <h2>System Snapshot</h2>
        <div class="meta-grid">
          <div><span>Drift Index</span><strong>{data['reward_drift']['drift_index']:.2f}</strong></div>
          <div><span>Curriculum Stage</span><strong>{escape(curriculum['current_stage'])}</strong></div>
          <div><span>Next Stage</span><strong>{escape(curriculum['next_stage'] or '-')}</strong></div>
          <div><span>Total Cost</span><strong>{data['cost']['total_cost']:.3f}</strong></div>
          <div><span>Low Score Blocks</span><strong>{failures['low_score_block']}</strong></div>
          <div><span>Verifier Reviews</span><strong>{failures['verifier_override_review']}</strong></div>
        </div>
      </article>

      <article class="card full">
        <h2>Prioritized Review Queue</h2>
        <p class="subtle">Items are ranked by review risk so operators can spend limited human bandwidth on the highest pressure cases first.</p>
        <table>
          <thead>
            <tr>
              <th>Iteration</th>
              <th>Node</th>
              <th>Auto Score</th>
              <th>Auto Decision</th>
              <th>Risk</th>
            </tr>
          </thead>
          <tbody>{review_items}</tbody>
        </table>
      </article>

      <article class="card half">
        <h2>Active Learning Candidates</h2>
        <p class="subtle">Near-threshold items that are most valuable for targeted labeling or calibration.</p>
        <table>
          <thead>
            <tr>
              <th>Iteration</th>
              <th>Score</th>
              <th>Uncertainty</th>
            </tr>
          </thead>
          <tbody>{active_learning_items}</tbody>
        </table>
      </article>

      <article class="card half">
        <h2>Policy Registry</h2>
        <p class="subtle">Registered reward policy versions available for replay, auditing, and staged rollout.</p>
        <ul class="clean">{policy_items}</ul>
      </article>

      <article class="card full">
        <h2>Recent Events</h2>
        <p class="subtle">Most recent experimental events emitted by the trainer, useful for operator audit trails.</p>
        <ul class="clean">{event_items}</ul>
      </article>
    </section>
  </main>
</body>
</html>
"""


def save_decision_console_html(console: DecisionConsole, path: str) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_decision_console_html(console), encoding="utf-8")
    return output


def _metric_card(label: str, value: int, note: str) -> str:
    return (
        '<article class="card metric-card">'
        f"<span>{escape(label)}</span>"
        f"<strong>{value}</strong>"
        f"<span>{escape(note)}</span>"
        "</article>"
    )
