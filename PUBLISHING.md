# Publishing PolyForge to GitHub

You run these — I can't push to your account directly. Three steps.

## 1. Create the repo on GitHub
Go to https://github.com/new
- Name: `polyforge`
- Description: "Audit MCP servers for reliability and route around dead ones."
- Public. Do NOT initialize with a README (you already have one).

## 2. Push from the unzipped folder
From inside the unzipped `polyforge/` directory:

```bash
git init
git add .
git commit -m "Initial commit: MCP server reliability auditor + fallback"
git branch -M main
git remote add origin https://github.com/AryanGonsalves/polyforge.git
git push -u origin main
```

## 3. Polish the repo page (5 minutes, high impact)
- Add topics (repo home → gear icon next to About): `mcp`, `ai-agents`,
  `reliability`, `llm`, `developer-tools`, `python`
- Confirm the README renders (it leads with the MCP value prop)
- Add a short tagline in the About box matching the README headline

## Before you post anywhere
- [ ] `pip install -e .` works from a clean clone
- [ ] `polyforge mcp-audit examples/mcp_servers.yaml` runs
- [ ] `python -m pytest tests/ -q` is green (24 tests)
- [ ] A demo GIF or screenshot of the colored audit output is in the README
      (devs trust seeing it run; record with asciinema or a simple screen grab)

## A note on a LICENSE file
`pyproject.toml` declares MIT. Add a real `LICENSE` file so it's unambiguous —
GitHub's "Add file → Create new file → LICENSE" gives you a one-click MIT
template with your name.
