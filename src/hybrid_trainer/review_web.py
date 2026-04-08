from __future__ import annotations

from html import escape
import json
from pathlib import Path

from .decision_console import DecisionConsole
from .review_permissions import ReviewPermissionPolicy
from .review_router import RoutedReviewBatch


def render_review_workbench_html(
    console: DecisionConsole,
    batch: RoutedReviewBatch,
    reviewer: str,
    role: str = "reviewer",
    permission_policy: ReviewPermissionPolicy | None = None,
) -> str:
    data = console.to_dict()
    policy = permission_policy or ReviewPermissionPolicy.default()
    role_policy = policy.resolve(role)
    allowed_decisions = list(role_policy.allowed_decisions)
    can_interact = role_policy.can_resolve and bool(allowed_decisions)
    can_export = role_policy.can_export and can_interact

    rows = "".join(
        _review_row(
            iteration=item.iteration,
            node=item.node.value,
            auto_score=item.auto_score,
            auto_decision=item.auto_decision.value,
            allowed_decisions=allowed_decisions,
            enabled=can_interact,
        )
        for item in batch.items
    ) or (
        '<tr><td colspan="5">No pending review items in the current budget window.</td></tr>'
    )

    policy_cards = "".join(
        (
            '<article class="role-card">'
            f"<strong>{escape(item.role)}</strong>"
            f"<span>{escape(item.description or 'No description')}</span>"
            f"<em>decisions: {escape(', '.join(item.allowed_decisions) or 'none')}</em>"
            f"<em>subjects: {escape(', '.join(item.allowed_subjects) or 'any')}</em>"
            f"<em>groups: {escape(', '.join(item.allowed_groups) or 'any')}</em>"
            f"<em>emails: {escape(', '.join(item.allowed_emails) or 'any')}</em>"
            f"<em>issuers: {escape(', '.join(item.allowed_issuers) or 'any')}</em>"
            "</article>"
        )
        for item in policy.roles.values()
    )
    status_text = (
        "Interactive session enabled. Exported JSON can be fed back into the CLI."
        if can_export
        else "Read-only session. This role can inspect the queue but cannot export decisions."
    )
    button_attrs = "" if can_export else ' disabled aria-disabled="true"'
    permission_payload = json.dumps(
        {
            "reviewer": reviewer,
            "role": role,
            "allowed_decisions": allowed_decisions,
            "allowed_subjects": list(role_policy.allowed_subjects),
            "allowed_groups": list(role_policy.allowed_groups),
            "allowed_emails": list(role_policy.allowed_emails),
            "allowed_issuers": list(role_policy.allowed_issuers),
            "can_export": can_export,
        },
        ensure_ascii=False,
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hybrid Trainer Review Workbench</title>
  <style>
    :root {{
      --bg: #f1efe9;
      --panel: rgba(255, 255, 255, 0.88);
      --ink: #1f2f2a;
      --muted: #61716d;
      --accent: #9d4f2c;
      --accent-soft: #efd1c0;
      --line: rgba(31, 47, 42, 0.12);
      --success: #2b7c58;
      --radius: 22px;
      --shadow: 0 22px 50px rgba(50, 45, 32, 0.14);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at top left, rgba(242, 208, 176, 0.68), transparent 28%),
        radial-gradient(circle at top right, rgba(175, 212, 198, 0.7), transparent 30%),
        linear-gradient(145deg, #f6f2ea 0%, #edf3ec 100%);
      color: var(--ink);
      font-family: "Trebuchet MS", Verdana, sans-serif;
    }}
    main {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 36px 20px 54px;
    }}
    .hero, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }}
    .hero {{
      padding: 28px 30px;
    }}
    .eyebrow {{
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--accent);
      font-size: 12px;
      margin-bottom: 12px;
    }}
    h1, h2 {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
    }}
    h1 {{
      font-size: clamp(2rem, 3vw, 3.3rem);
      line-height: 1.05;
    }}
    p {{
      margin: 14px 0 0;
      color: var(--muted);
      line-height: 1.7;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: 18px;
      margin-top: 20px;
    }}
    .panel {{
      padding: 22px;
    }}
    .span-4 {{ grid-column: span 4; }}
    .span-5 {{ grid-column: span 5; }}
    .span-7 {{ grid-column: span 7; }}
    .span-8 {{ grid-column: span 8; }}
    .span-12 {{ grid-column: span 12; }}
    .meta {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-top: 16px;
    }}
    .meta div, .role-card {{
      padding: 14px;
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.56);
      border: 1px solid var(--line);
    }}
    .meta strong, .role-card strong {{
      display: block;
      margin-top: 6px;
      font-size: 1rem;
    }}
    .role-list {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 16px;
    }}
    .role-card span, .role-card em {{
      display: block;
      color: var(--muted);
      margin-top: 8px;
      font-style: normal;
      line-height: 1.5;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 16px;
    }}
    th, td {{
      text-align: left;
      padding: 12px 10px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }}
    th {{
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 0.74rem;
      color: var(--muted);
    }}
    select, textarea, button {{
      width: 100%;
      border-radius: 14px;
      border: 1px solid var(--line);
      padding: 10px 12px;
      font: inherit;
      background: rgba(255, 255, 255, 0.82);
      color: var(--ink);
    }}
    textarea {{
      min-height: 88px;
      resize: vertical;
    }}
    button {{
      cursor: pointer;
      background: linear-gradient(135deg, var(--accent) 0%, #c86a3d 100%);
      color: white;
      font-weight: 600;
      border: none;
      box-shadow: 0 12px 26px rgba(157, 79, 44, 0.24);
    }}
    button[disabled] {{
      cursor: not-allowed;
      background: #b7b7b7;
      box-shadow: none;
      opacity: 0.7;
    }}
    .callout {{
      margin-top: 16px;
      padding: 14px 16px;
      border-radius: 16px;
      background: rgba(43, 124, 88, 0.09);
      color: var(--ink);
      border: 1px solid rgba(43, 124, 88, 0.18);
    }}
    .callout strong {{
      color: var(--success);
    }}
    .footer-note {{
      font-size: 0.92rem;
      color: var(--muted);
      margin-top: 16px;
      line-height: 1.6;
    }}
    pre {{
      margin: 16px 0 0;
      padding: 16px;
      border-radius: 18px;
      background: #1f2825;
      color: #edf3ef;
      overflow-x: auto;
      font-size: 0.9rem;
    }}
    @media (max-width: 980px) {{
      .span-4, .span-5, .span-7, .span-8 {{ grid-column: span 12; }}
      .meta, .role-list {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="eyebrow">Hybrid Self-Improvement Trainer</div>
      <h1>Web Review Workbench</h1>
      <p>
        Export reviewer decisions as JSON and feed them back into the CLI with
        <code>--review-decisions-input</code>. The page enforces role-level decision permissions
        so the exported payload matches the workflow each reviewer is allowed to perform.
      </p>
      <div class="meta">
        <div><span>Reviewer</span><strong>{escape(reviewer)}</strong></div>
        <div><span>Role</span><strong>{escape(role_policy.role)}</strong></div>
        <div><span>Pending In Budget</span><strong>{len(batch.items)}</strong></div>
        <div><span>Queue Pending</span><strong>{data['review_queue']['pending_count']}</strong></div>
      </div>
      <div class="callout"><strong>Session Status:</strong> {escape(status_text)}</div>
    </section>

    <section class="grid">
      <article class="panel span-8">
        <h2>Review Queue</h2>
        <p>Prioritized items from the current review budget. Decisions exported from this page are compatible with the existing CLI backfill flow.</p>
        <table>
          <thead>
            <tr>
              <th>Iteration</th>
              <th>Node</th>
              <th>Auto Score</th>
              <th>Auto Decision</th>
              <th>Decision Workspace</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
        <button id="export-decisions"{button_attrs}>Download review_decisions.json</button>
        <pre id="json-preview">{{"decisions":[]}}</pre>
        <div class="footer-note">
          Suggested backfill command:
          <code>python -m hybrid_trainer.cli --review-decisions-input review_decisions.json --output artifacts/run_summary.json</code>
        </div>
      </article>

      <article class="panel span-4">
        <h2>Permission Policy</h2>
        <p>Roles describe what each reviewer can do in the browser before exporting a decision file.</p>
        <div class="role-list">{policy_cards}</div>
      </article>

      <article class="panel span-5">
        <h2>Decision Snapshot</h2>
        <div class="meta">
          <div><span>Approve</span><strong>{data['dashboard']['metrics']['approve']}</strong></div>
          <div><span>Review</span><strong>{data['dashboard']['metrics']['review']}</strong></div>
          <div><span>Block</span><strong>{data['dashboard']['metrics']['block']}</strong></div>
          <div><span>Consensus</span><strong>{data['review_consensus']['consensus_groups']}</strong></div>
        </div>
      </article>

      <article class="panel span-7">
        <h2>Operator Guidance</h2>
        <p>{escape(data['strategy']['reason'])}</p>
        <div class="callout">
          <strong>Current Strategy:</strong> {escape(data['strategy']['current'])}
          <br>
          <strong>Recommended:</strong> {escape(data['strategy']['recommended'])}
          <br>
          <strong>Current Curriculum:</strong> {escape(data['curriculum']['current_stage'])}
        </div>
      </article>
    </section>
  </main>
  <script>
    const permissionContext = {permission_payload};
    const reviewer = permissionContext.reviewer;
    const role = permissionContext.role;
    const canExport = permissionContext.can_export;

    function collectDecisions() {{
      const rows = Array.from(document.querySelectorAll("[data-review-item]"));
      const decisions = rows.flatMap((row) => {{
        const iteration = Number(row.dataset.iteration);
        const decisionField = row.querySelector("select");
        const noteField = row.querySelector("textarea");
        if (!decisionField || !decisionField.value) {{
          return [];
        }}
        return [{{
          iteration,
          final_decision: decisionField.value,
          reviewer,
          note: noteField ? noteField.value : "",
        }}];
      }});
      return {{
        role,
        reviewer,
        decisions,
      }};
    }}

    function refreshPreview() {{
      const payload = collectDecisions();
      document.getElementById("json-preview").textContent = JSON.stringify(payload, null, 2);
    }}

    function downloadPayload() {{
      if (!canExport) {{
        return;
      }}
      const payload = collectDecisions();
      const blob = new Blob([JSON.stringify(payload, null, 2)], {{ type: "application/json" }});
      const href = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = href;
      link.download = "review_decisions.json";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(href);
    }}

    document.querySelectorAll("select, textarea").forEach((element) => {{
      element.addEventListener("input", refreshPreview);
    }});
    document.getElementById("export-decisions").addEventListener("click", downloadPayload);
    refreshPreview();
  </script>
</body>
</html>
"""


def save_review_workbench_html(
    console: DecisionConsole,
    batch: RoutedReviewBatch,
    path: str,
    reviewer: str,
    role: str = "reviewer",
    permission_policy: ReviewPermissionPolicy | None = None,
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render_review_workbench_html(
            console=console,
            batch=batch,
            reviewer=reviewer,
            role=role,
            permission_policy=permission_policy,
        ),
        encoding="utf-8",
    )
    return output


def _review_row(
    iteration: int,
    node: str,
    auto_score: float,
    auto_decision: str,
    allowed_decisions: list[str],
    enabled: bool,
) -> str:
    options = "".join(
        f'<option value="{escape(item)}">{escape(item)}</option>'
        for item in allowed_decisions
    )
    disabled = "" if enabled else " disabled"
    select_html = (
        f'<select aria-label="decision-{iteration}"{disabled}>'
        '<option value="">Select decision</option>'
        f"{options}</select>"
    )
    note_html = (
        f'<textarea aria-label="note-{iteration}" placeholder="Add reviewer note"{disabled}></textarea>'
    )
    return (
        f'<tr data-review-item data-iteration="{iteration}">'
        f"<td>{iteration}</td>"
        f"<td>{escape(node)}</td>"
        f"<td>{auto_score:.2f}</td>"
        f"<td>{escape(auto_decision)}</td>"
        f"<td>{select_html}{note_html}</td>"
        "</tr>"
    )
