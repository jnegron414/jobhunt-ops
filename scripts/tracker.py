"""Application tracker CLI. The morning command is `today`.

Usage: .venv/bin/python scripts/tracker.py <command> ...
(alias suggestion for your shell: alias track='~/jobhunt-ops/.venv/bin/python ~/jobhunt-ops/scripts/tracker.py')
"""
import sys
from datetime import date, datetime
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).parent.parent))
import config  # noqa: E402


def now():
    return datetime.now().isoformat(timespec="seconds")


def log_event(conn, app_id, etype, detail=""):
    conn.execute("INSERT INTO events (application_id, ts, type, detail) VALUES (?,?,?,?)",
                 (app_id, now(), etype, detail))


def get_app(conn, app_id):
    row = conn.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()
    if not row:
        raise click.ClickException(f"no application with id {app_id}")
    return row


def company_tiers():
    return {t["name"].lower(): t.get("tier", 3) for t in config.load_targets()}


@click.group()
def cli():
    """Job application tracker."""


@cli.command()
@click.argument("company")
@click.argument("role")
@click.option("--url", default="")
@click.option("--source", default="", help="e.g. digest, referral, recruiter, cold")
@click.option("--stage", default="lead", type=click.Choice(config.STAGES))
@click.option("--jd", type=click.Path(exists=True), default=None,
              help="Path to a file with the JD text (stored; postings go 404)")
def add(company, role, url, source, stage, jd):
    """Add an application (default stage: lead)."""
    jd_text = Path(jd).read_text() if jd else None
    conn = config.get_db()
    cur = conn.execute(
        "INSERT INTO applications (company, role, url, source, stage, applied_at, updated_at, jd_text) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (company, role, url, source, stage,
         now() if stage != "lead" else None, now(), jd_text),
    )
    log_event(conn, cur.lastrowid, "created", f"stage={stage} source={source}")
    conn.commit()
    click.echo(f"[{cur.lastrowid}] {company} — {role} ({stage})"
               + (" — JD stored" if jd_text else ""))


@cli.command()
@click.argument("app_id", type=int)
@click.argument("stage", type=click.Choice(config.STAGES))
@click.option("--note", default="")
def move(app_id, stage, note):
    """Move an application to a new stage."""
    conn = config.get_db()
    app = get_app(conn, app_id)
    conn.execute("UPDATE applications SET stage=?, updated_at=?, "
                 "applied_at=COALESCE(applied_at, ?) WHERE id=?",
                 (stage, now(), now() if stage != "lead" else None, app_id))
    log_event(conn, app_id, "stage", f"{app['stage']} -> {stage}" + (f" | {note}" if note else ""))
    conn.commit()
    click.echo(f"[{app_id}] {app['company']}: {app['stage']} -> {stage}")


@cli.command()
@click.argument("app_id", type=int)
@click.argument("text")
def note(app_id, text):
    """Attach a note (also logged as an event)."""
    conn = config.get_db()
    app = get_app(conn, app_id)
    merged = (app["notes"] + "\n" if app["notes"] else "") + f"{date.today()}: {text}"
    conn.execute("UPDATE applications SET notes=?, updated_at=? WHERE id=?",
                 (merged, now(), app_id))
    log_event(conn, app_id, "note", text)
    conn.commit()
    click.echo(f"[{app_id}] noted.")


@cli.command("next")
@click.argument("app_id", type=int)
@click.argument("action")
@click.option("--date", "when", required=True, help="YYYY-MM-DD")
def next_action(app_id, action, when):
    """Set the next action + date for an application."""
    datetime.strptime(when, "%Y-%m-%d")  # validate
    conn = config.get_db()
    get_app(conn, app_id)
    conn.execute("UPDATE applications SET next_action=?, next_action_date=?, updated_at=? WHERE id=?",
                 (action, when, now(), app_id))
    log_event(conn, app_id, "next_action", f"{when}: {action}")
    conn.commit()
    click.echo(f"[{app_id}] next: {action} on {when}")


def _last_activity(conn, app_id):
    row = conn.execute("SELECT MAX(ts) m FROM events WHERE application_id=?", (app_id,)).fetchone()
    return row["m"]


@cli.command()
@click.option("--stage", type=click.Choice(config.STAGES), default=None)
@click.option("--tier", type=int, default=None)
@click.option("--stale", is_flag=True, help="only apps with no activity for 7+ days")
def ls(stage, tier, stale):
    """List applications."""
    conn = config.get_db()
    q, params = "SELECT * FROM applications", []
    if stage:
        q += " WHERE stage=?"
        params.append(stage)
    rows = conn.execute(q + " ORDER BY updated_at DESC", params).fetchall()
    tiers = company_tiers()
    out = 0
    for r in rows:
        t = tiers.get(r["company"].lower(), "-")
        if tier is not None and t != tier:
            continue
        last = _last_activity(conn, r["id"]) or r["updated_at"] or now()
        days_quiet = (date.today() - datetime.fromisoformat(last).date()).days
        if stale and (days_quiet < 7 or r["stage"] not in config.ACTIVE_STAGES):
            continue
        na = f" | next: {r['next_action']} ({r['next_action_date']})" if r["next_action"] else ""
        click.echo(f"[{r['id']:>3}] {r['stage']:<11} T{t} {r['company']} — {r['role']}"
                   f" | quiet {days_quiet}d{na}")
        out += 1
    if not out:
        click.echo("(nothing)")


@cli.command()
def today():
    """Morning view: due next-actions + stale active applications."""
    conn = config.get_db()
    t = date.today().isoformat()
    due = conn.execute(
        "SELECT * FROM applications WHERE next_action_date IS NOT NULL AND next_action_date <= ? "
        "AND stage IN ({}) ORDER BY next_action_date".format(",".join("?" * len(config.ACTIVE_STAGES))),
        [t, *config.ACTIVE_STAGES]).fetchall()
    click.echo(f"# Today — {t}\n")
    if due:
        click.echo("## Due")
        for r in due:
            click.echo(f"- [{r['id']}] {r['company']} — {r['next_action']} (due {r['next_action_date']})")
    else:
        click.echo("## Due\n- nothing due")
    click.echo("\n## Stale (active, quiet 7+ days)")
    stale_found = False
    for r in conn.execute("SELECT * FROM applications WHERE stage IN ({})".format(
            ",".join("?" * len(config.ACTIVE_STAGES))), config.ACTIVE_STAGES).fetchall():
        last = _last_activity(conn, r["id"]) or r["updated_at"] or now()
        days_quiet = (date.today() - datetime.fromisoformat(last).date()).days
        if days_quiet >= 7:
            click.echo(f"- [{r['id']}] {r['company']} — {r['role']} ({r['stage']}, quiet {days_quiet}d)")
            stale_found = True
    if not stale_found:
        click.echo("- none")


@cli.command()
def stats():
    """Funnel counts, response rate, avg days in stage."""
    conn = config.get_db()
    click.echo("## Funnel")
    total = 0
    for s in config.STAGES:
        n = conn.execute("SELECT COUNT(*) c FROM applications WHERE stage=?", (s,)).fetchone()["c"]
        total += n
        if n:
            click.echo(f"- {s:<12} {n}")
    click.echo(f"- {'TOTAL':<12} {total}")
    applied = conn.execute("SELECT COUNT(*) c FROM applications WHERE applied_at IS NOT NULL").fetchone()["c"]
    responded = conn.execute(
        "SELECT COUNT(DISTINCT application_id) c FROM events WHERE type='stage' "
        "AND (detail LIKE '%-> screen%' OR detail LIKE '%-> tech%' OR detail LIKE '%-> onsite%' "
        "OR detail LIKE '%-> offer%')").fetchone()["c"]
    if applied:
        click.echo(f"\nResponse rate: {responded}/{applied} applied -> past screen door "
                   f"({100 * responded // applied}%)")
    moves = conn.execute("SELECT application_id, ts FROM events WHERE type IN ('created','stage') "
                         "ORDER BY application_id, ts").fetchall()
    gaps, prev = [], None
    for m in moves:
        if prev and prev["application_id"] == m["application_id"]:
            gaps.append((datetime.fromisoformat(m["ts"]) - datetime.fromisoformat(prev["ts"])).days)
        prev = m
    if gaps:
        click.echo(f"Avg days-in-stage (completed stages): {sum(gaps) / len(gaps):.1f}")


if __name__ == "__main__":
    cli()
