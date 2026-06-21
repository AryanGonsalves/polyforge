# Validation Plan — before building more

Goal: find out whether real agent developers want this, *before* investing in
the next features. The discipline here is the whole point — strong signal from
blog posts is not the same as proven demand.

## The one question to answer
"Will agent developers run this on their real MCP setup and act on the output?"

Everything below is in service of answering that — cheaply, in ~2 weeks.

## What 'validated' looks like (set the bar before you start)
- 5+ developers run `mcp-audit` on their *own* servers (not the example)
- 2+ say it caught something they didn't know / would change a decision
- At least 1 unprompted "when's the GitHub-API version coming?" type ask
If you hit those, build roadmap item 2. If you get crickets, the niche isn't
real *for a tool* yet — and you've spent days, not months, learning that.

## Step 1 — Ship the repo (Day 1)
Follow PUBLISHING.md. Repo public, README with a demo GIF, 24 tests green.

## Step 2 — Talk to 5 people BEFORE the big post (Days 2–5)
Posting to HN once is a single shot; do small first.
- Find people already complaining about MCP reliability (the dev.to / Reddit
  threads, MCP Discords). Reply helpfully, then: "I built a small scanner for
  exactly this — would you run it on your servers and tell me if the scores
  match your gut?"
- Watch where they get confused installing or reading output. Fix that first.
- This is qualitative. You're listening for "oh, that one IS sketchy" moments.

## Step 3 — The public launch (Week 2)
Once 5 people have run it and obvious friction is fixed, post the Show HN
(draft in LAUNCH_show_hn.md) plus r/AI_Agents and r/LocalLLaMA.
- Lead with the "half are abandoned" stat.
- Be present in comments for 2 hours.

## Step 4 — Instrument what you can (passive)
You can't see who runs a pip package, so use proxies:
- GitHub stars / forks / issues opened
- Comments asking for features (especially the GitHub-API auto-gather)
- Anyone who opens a PR or files a "my server scored wrong" issue — gold

## Step 5 — Decide (end of Week 2)
- Hit the bar → build roadmap item 2 (auto-gather signals from GitHub API).
- Mixed → narrow further or fix the specific objection people raised.
- Crickets → keep it as a strong portfolio piece (see below) and move on.

## Either way, it already pays off
Even if demand is thin, this repo is a genuinely strong portfolio artifact for
your job search: clean architecture, a real rubric, 24 tests, a working CLI,
and evidence you researched a market and made disciplined pivots. Frame it
honestly in interviews as "found a fresh gap in MCP reliability, built and
shipped a scanner, validated with real users" — that story is worth as much as
the code.

## What NOT to do
- Don't build roadmap items 2–5 before Step 5. That's the trap we already
  avoided twice.
- Don't widen scope back toward "universal platform." The wins here came from
  narrowing.
- Don't over-claim. "Early, rubric not yet validated" is the honest and
  effective framing.
