#!/bin/bash
# Export path so python3 from Homebrew or Frameworks can be found
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"

cd /Users/sravya/costco

TODAY=$(date '+%Y-%m-%d')
CURRENT_HOUR=$(date +'%H')
CURRENT_HOUR=${CURRENT_HOUR#0} # remove leading zero to avoid octal interpretation

# Check if we already ran today
if grep -q "Costco Agent — $TODAY" agent.log 2>/dev/null; then
    echo "[$TODAY $(date '+%H:%M:%S')] Agent already ran today. Skipping."
    exit 0
fi

# Check if it's before 11 AM.
if [ "$CURRENT_HOUR" -lt 11 ]; then
    echo "[$TODAY $(date '+%H:%M:%S')] It is before 11 AM ($CURRENT_HOUR:00), waiting for scheduled launchd time. Skipping."
    exit 0
fi

# Run the agent!
echo "[$TODAY $(date '+%H:%M:%S')] Catch-up/scheduled trigger fired. Starting agent..."
python3 src/agent.py
