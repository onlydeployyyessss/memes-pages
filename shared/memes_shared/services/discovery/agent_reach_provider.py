"""Agent-Reach provider (EXPERIMENTAL, optional).

Evaluation summary (verified against the upstream repository
https://github.com/Panniantong/Agent-Reach on 2026-09-04):

* Agent-Reach is a CLI *capability layer*: it installs/routes/health-checks
  upstream open-source backends (`opencli`, `twitter-cli`, `bili-cli`,
  `yt-dlp`, `gh`, `mcporter`, Jina Reader, …) for 15 platforms.
* Its own stable commands are `agent-reach doctor [--json]`,
  `agent-reach install --env=auto` and `agent-reach configure …`. Reading a
  URL / searching is performed by calling the *upstream* tools it manages.
* Therefore this provider uses `doctor --json` for availability probing and
  executes a user-configured command template (from the source's
  `config.command`) whose stdout is parsed as JSON. It is never enabled by
  default and the rest of the system works fully without it.

Integration contract:
  source.source_type == "agent_reach"
  source.url         = the page/profile to read (optional)
  source.config      = {
      "command": "twitter search memes --json {limit}",  # upstream CLI call
      # placeholders available: {url} {query} {limit}
      "query": "memes"
  }
Output parsing: JSON array, {"items":[…]} or JSON-lines.
"""
from __future__ import annotations

import json
import shlex
import subprocess

from memes_shared.config import get_settings
from memes_shared.logging_setup import get_logger
from memes_shared.models import ContentSource, RssFeed
from memes_shared.services.discovery.authorized_feed_provider import _coerce_item
from memes_shared.services.discovery.base import (
    DiscoveryItem,
    DiscoveryProvider,
    DiscoveryUnavailable,
)
from memes_shared.utils.timeutil import utcnow

log = get_logger("memes.discovery.agentreach")

_DOCTOR_CACHE: dict = {"checked_at": None, "available": False, "report": {}}
_CACHE_TTL_SECONDS = 300


class AgentReachProvider(DiscoveryProvider):
    name = "agent_reach"

    def supports(self, source_type: str) -> bool:
        cfg = get_settings()
        enabled = cfg.agent_reach_enabled
        try:
            import memes_shared.services.settings as settings_svc
            enabled = enabled or bool(
                settings_svc.DEFAULT_SETTINGS["discovery"]["agent_reach_enabled"]
            )
        except Exception:  # noqa: BLE001
            pass
        return source_type == "agent_reach" and enabled

    # ── Availability probing ─────────────────────────────────────────
    def probe(self, force: bool = False) -> dict:
        """Return {'available': bool, 'report': <doctor --json output>}."""
        from datetime import datetime, timedelta

        now = utcnow()
        if (
            not force
            and _DOCTOR_CACHE["checked_at"]
            and now - _DOCTOR_CACHE["checked_at"] < timedelta(seconds=_CACHE_TTL_SECONDS)
        ):
            return {"available": _DOCTOR_CACHE["available"], "report": _DOCTOR_CACHE["report"]}

        bin_ = get_settings().agent_reach_bin
        try:
            proc = subprocess.run(
                [bin_, "doctor", "--json"], capture_output=True, timeout=60, check=False
            )
            available = proc.returncode == 0
            report: dict = {}
            try:
                report = json.loads(proc.stdout.decode() or "{}")
            except json.JSONDecodeError:
                report = {"stdout": proc.stdout.decode()[:500], "stderr": proc.stderr.decode()[:500]}
        except (FileNotFoundError, subprocess.TimeoutExpired):
            available, report = False, {"error": f"'{bin_}' binary not found"}
        _DOCTOR_CACHE.update(checked_at=now, available=available, report=report)
        return {"available": available, "report": report}

    def fetch(self, source: ContentSource, feed: RssFeed | None = None):
        cfg = get_settings()
        if not cfg.agent_reach_enabled:
            raise DiscoveryUnavailable(
                "Agent-Reach provider is disabled (set MEMES_AGENT_REACH_ENABLED=true)"
            )
        probe = self.probe()
        if not probe["available"]:
            raise DiscoveryUnavailable(
                "agent-reach doctor reported the tool is not operational — "
                "run `agent-reach doctor` for details"
            )

        cmd_tpl = (source.config or {}).get("command") or ""
        if not cmd_tpl:
            raise DiscoveryUnavailable(
                "agent_reach source requires config.command "
                "(e.g. 'twitter search memes --json {limit}')"
            )
        command = cmd_tpl.format(
            url=source.url or "",
            query=(source.config or {}).get("query", ""),
            limit=(source.config or {}).get("limit", 20),
        )
        try:
            proc = subprocess.run(
                shlex.split(command), capture_output=True, timeout=180, check=False
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            raise DiscoveryUnavailable(f"agent-reach command failed: {e}") from e
        if proc.returncode != 0:
            raise DiscoveryUnavailable(
                f"command exited {proc.returncode}: {proc.stderr.decode()[:300]}"
            )
        items = self._parse_output(proc.stdout.decode())
        category = source.categories[0] if source.categories else "memes"
        return [_coerce_item(i, category) for i in items], {"command": command}

    @staticmethod
    def _parse_output(stdout: str) -> list[dict]:
        text = stdout.strip()
        if not text:
            return []
        try:
            data = json.loads(text)
            rows = data if isinstance(data, list) else (data.get("items") or [])
            return [r for r in rows if isinstance(r, dict)]
        except json.JSONDecodeError:
            pass
        rows: list[dict] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    rows.append(obj)
            except json.JSONDecodeError:
                continue
        return rows
