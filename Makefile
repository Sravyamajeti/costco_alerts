# ──────────────────────────────────────────────────────────────────────────────
# Costco Price Protection Agent — Makefile
# ──────────────────────────────────────────────────────────────────────────────

PYTHON  = /Library/Frameworks/Python.framework/Versions/3.12/bin/python3
SRC_DIR = src
LOG     = agent.log
PLIST   = $(HOME)/Library/LaunchAgents/com.sravya.costco-agent.plist
TODAY   = $(shell date '+%Y-%m-%d')

.PHONY: help run dry-run status logs logs-today \
        agent-start agent-stop agent-reload agent-enable agent-disable \
        test-email install-deps push

# ── Default ───────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  Costco Price Protection Agent"
	@echo "  ─────────────────────────────────────────────────────"
	@echo "  make run           Run the agent now (scrape + email)"
	@echo "  make dry-run       Simulate a run without sending emails"
	@echo "  make status        Did the agent run today? Any alerts?"
	@echo "  make logs          Stream the full agent log (tail -f)"
	@echo "  make logs-today    Show only today's log output"
	@echo "  ─────────────────────────────────────────────────────"
	@echo "  make agent-start   Run the agent via launchd right now"
	@echo "  make agent-stop    Stop a currently-running agent job"
	@echo "  make agent-reload  Reload plist after editing it"
	@echo "  make agent-enable  Re-enable daily scheduling"
	@echo "  make agent-disable Disable daily scheduling (keeps plist)"
	@echo "  ─────────────────────────────────────────────────────"
	@echo "  make push          Add all changes, commit, and push to Git"
	@echo "  make test-email    Send a test digest email"
	@echo "  make install-deps  Install Python dependencies"
	@echo ""

# ── Run ───────────────────────────────────────────────────────────────────────
run:
	@echo "🚀 Running Costco agent..."
	cd $(SRC_DIR) && $(PYTHON) agent.py

dry-run:
	@echo "🧪 Dry run (no scraping, no emails)..."
	cd $(SRC_DIR) && $(PYTHON) agent.py --dry-run

# ── Status: did it run today? ─────────────────────────────────────────────────
status:
	@echo ""
	@echo "📅 Checking if agent ran on $(TODAY)..."
	@if grep -q "Costco Agent — $(TODAY)" $(LOG) 2>/dev/null; then \
		echo "  ✅ YES — agent ran today"; \
		echo ""; \
		grep -A2 "Costco Agent — $(TODAY)" $(LOG) | tail -3; \
		echo ""; \
		LAST_LINE=$$(awk "/Costco Agent — $$(date '+%Y-%m-%d')/,0" $(LOG) | grep "Done\." | tail -1); \
		if [ -n "$$LAST_LINE" ]; then \
			echo "  Last result: $$LAST_LINE"; \
		else \
			echo "  Last result: ❌ Crashed or still running"; \
		fi \
	else \
		echo "  ❌ NO — agent has NOT run today yet"; \
		LAST=$$(grep "Costco Agent —" $(LOG) | tail -1); \
		echo "  Last ran:    $$LAST"; \
	fi
	@echo ""

# ── Logs ─────────────────────────────────────────────────────────────────────
logs:
	@tail -f $(LOG)

logs-today:
	@echo "📋 Log output for $(TODAY):"
	@echo ""
	@awk "/Costco Agent — $(TODAY)/,0" $(LOG) || echo "  (no entries for today yet)"

# ── launchd agent management ──────────────────────────────────────────────────
agent-start:
	@echo "▶️  Triggering agent via launchd..."
	launchctl start com.sravya.costco-agent

agent-stop:
	@echo "⏹  Stopping agent..."
	launchctl stop com.sravya.costco-agent

agent-reload:
	@echo "🔄 Reloading plist..."
	launchctl unload $(PLIST)
	launchctl load $(PLIST)
	@echo "✅ Reloaded."

agent-enable:
	@echo "✅ Enabling daily schedule..."
	launchctl load $(PLIST)

agent-disable:
	@echo "🚫 Disabling daily schedule (plist kept)..."
	launchctl unload $(PLIST)

# ── Utilities ─────────────────────────────────────────────────────────────────
test-email:
	@echo "📧 Sending test email..."
	cd $(SRC_DIR) && $(PYTHON) notifier.py --test

install-deps:
	$(PYTHON) -m pip install -r requirements.txt

# ── Git ───────────────────────────────────────────────────────────────────────
push:
	@echo "📦 Pushing changes to Git..."
	git add .
	git commit -m "Update agent files" || echo "No changes to commit."
	git push

