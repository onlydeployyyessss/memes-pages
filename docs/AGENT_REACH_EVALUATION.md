# 🔎 Agent-Reach evaluation

**Repository inspected:** https://github.com/Panniantong/Agent-Reach
(evaluated 2026-09-04 via the repo, `llms.txt` and `docs/README_en.md`)

## What Agent-Reach actually is

> "Give your AI agent eyes to see the internet. Agent Reach installs, routes,
> and health-checks upstream tools for 15 platforms — Twitter/X, Reddit,
> Facebook, Instagram, YouTube, GitHub, Bilibili, XiaoHongShu, LinkedIn, V2EX,
> Xueqiu, Xiaoyuzhou Podcast, RSS, web search, and any web page. One install,
> zero API fees."

Key verified facts:

- It is a **Python CLI capability layer** (`pip install agent-reach`), not a
  content API. Its own stable surface is `agent-reach doctor [--json]`,
  `agent-reach install --env=auto`, `agent-reach configure …`.
- Actual reading/searching is done by **upstream backends** it manages
  (`opencli`, `twitter-cli`, `bili-cli`, `yt-dlp`, `gh`, `mcporter`, Jina
  Reader…), several of which require **browser cookies / login sessions**
  (Twitter, Reddit, Facebook, Instagram, XiaoHongShu, Xueqiu).
- Several backends are scraping-based and platform-hostility-prone by the
  project's own admission ("Reddit — server IPs get 403'd"; backends rotate
  when platforms block them).

## Suitability for Memes Pages

| Requirement | Verdict |
|---|---|
| Trend *research* across social platforms | ✅ good fit (search/read trending posts) |
| Reliable hands-off server automation | ⚠️ cookie/login backends decay; needs babysitting |
| Media acquisition for republishing | ❌ not its purpose; upstream `yt-dlp` exists but platform ToS vary |
| Hard dependency risk | high if unmanaged — the project itself swaps backends frequently |

## Decision

**Integrated as an optional, non-blocking discovery provider — disabled by
default.** The rest of the system (RSS, authorized feeds, pipeline,
publishing) works 100% without it.

### Integration contract (`services/discovery/agent_reach_provider.py`)

- Availability probing: runs `agent-reach doctor --json` (5-min result cache);
  when the tool is missing/broken the provider raises
  `DiscoveryUnavailable` and the automation loop continues with other providers.
- Discovery: executes the **user-configured command template** stored on the
  source (`source.config.command`, e.g. `twitter search memes --json {limit}`),
  because read/search commands live in upstream tools, not in agent-reach
  itself. Output parsed as JSON array, `{"items": …}` or JSON-lines and mapped
  through the standard `DiscoveryItem` coercer.
- Enable path: install the CLI (`pip install agent-reach` + backends), set
  `MEMES_AGENT_REACH_ENABLED=true`, add a source with
  `source_type = agent_reach`, and (optionally) allow it in Settings →
  Discovery.

### Guardrails

- Never enabled by default; never a dependency in `requirements.txt`.
- All failures are logged per-source and never halt Trend Hunter.
- The abstraction (`DiscoveryProvider` interface) means future providers
  (Telegram channels, YouTube RSS, partner APIs…) plug in without core changes.
