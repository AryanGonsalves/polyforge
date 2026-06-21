# Show HN draft — PolyForge (MCP reliability)

## Title (pick one)
- Show HN: I audited my agent's MCP servers and half looked abandoned, so I built a scanner
- Show HN: PolyForge – Score your MCP servers for reliability and route around dead ones
- Show HN: A CLI that fails your CI if your AI agent depends on a dead MCP server

## Body

A recent audit of ~1,800 public MCP servers found more than half abandoned. The
failure mode is nasty: when an agent calls a broken or drifted MCP tool, the
model usually doesn't crash — it improvises around the bad response and keeps
going, quietly corrupting everything downstream. No exception, no alert.

PolyForge scores each MCP server your agent depends on against a reliability
rubric (commit recency, contributor count, CI status, unpatched CVEs, clean
install, uptime, schema stability) and buckets them: production-ready / use-with
-fallback / dead. A single-maintainer repo with stale commits gets flagged as
dead — the highest-signal abandonment indicator. Then a fallback router resolves
each capability to the healthiest server and skips the dead ones.

    pip install polyforge
    polyforge mcp-audit your_servers.yaml

It exits non-zero if anything's dead, so you can drop it into CI to stop a PR
that wires in an abandoned server.

Honest status: this is early and the rubric weights are a sensible default, not
yet validated against a big labeled set of real servers. Right now signals come
from a manifest; auto-gathering them from the GitHub API is the next step. I'd
especially love feedback on (1) whether the production/light/dead buckets match
your intuition, (2) what signal you'd add, and (3) whether you'd actually want
the fallback router to execute the MCP calls or just recommend.

Repo: https://github.com/AryanGonsalves/polyforge

## Notes for posting
- Post Tue–Thu, ~8-10am ET.
- Have the README demo GIF in place BEFORE posting.
- The "half are abandoned" stat is the hook — lead with it.
- Reply to every comment in the first 2 hours; engagement drives ranking.
- Keep the honest "early, not yet validated" framing — HN rewards it and it's true.

## Where else to post (in order of fit)
1. r/LocalLLaMA and r/AI_Agents — active MCP discussion, your exact audience
2. dev.to — the "52% of MCP servers are dead" posts live here; reply/cross-post
3. MCP / agent Discord communities — share as a tool, ask for feedback
4. Lobsters (need an invite) — high-signal dev crowd
5. Product Hunt — later, once polished
