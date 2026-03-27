#!/bin/bash
# Export path so python3 from Homebrew or Frameworks can be found
export PATH="/Library/Frameworks/Python.framework/Versions/3.12/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"

cd /Users/sravya/costco

# Run the agent!
python3 src/agent.py
