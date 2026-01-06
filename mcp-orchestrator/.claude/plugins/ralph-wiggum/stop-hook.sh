#!/bin/bash
# Ralph Wiggum Stop Hook
# Intercepts Claude's exit and continues if completion promise not found

RALPH_STATE_FILE="${RALPH_STATE_FILE:-.claude/ralph-state.json}"
RALPH_LOG_FILE="${RALPH_LOG_FILE:-.claude/ralph.log}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$RALPH_LOG_FILE"
}

# Check if Ralph loop is active
if [ ! -f "$RALPH_STATE_FILE" ]; then
    # No active Ralph loop, allow normal exit
    exit 0
fi

# Read state
ACTIVE=$(jq -r '.active // false' "$RALPH_STATE_FILE" 2>/dev/null)
ITERATION=$(jq -r '.iteration // 0' "$RALPH_STATE_FILE" 2>/dev/null)
MAX_ITERATIONS=$(jq -r '.max_iterations // 50' "$RALPH_STATE_FILE" 2>/dev/null)
COMPLETION_PROMISE=$(jq -r '.completion_promise // "DONE"' "$RALPH_STATE_FILE" 2>/dev/null)
ORIGINAL_PROMPT=$(jq -r '.prompt // ""' "$RALPH_STATE_FILE" 2>/dev/null)

if [ "$ACTIVE" != "true" ]; then
    exit 0
fi

log "Ralph iteration $ITERATION / $MAX_ITERATIONS"

# Check iteration limit
if [ "$ITERATION" -ge "$MAX_ITERATIONS" ]; then
    log "Max iterations reached, stopping"
    echo '{"active": false}' > "$RALPH_STATE_FILE"
    echo "RALPH: Max iterations ($MAX_ITERATIONS) reached. Stopping."
    exit 0
fi

# Check for completion promise in recent output/files
# This is a simplified check - in reality would check Claude's output
PROMISE_FOUND=$(grep -r "<promise>$COMPLETION_PROMISE</promise>" . 2>/dev/null | head -1)

if [ -n "$PROMISE_FOUND" ]; then
    log "Completion promise found: $PROMISE_FOUND"
    echo '{"active": false}' > "$RALPH_STATE_FILE"
    echo "RALPH: Completion promise found. Task complete!"
    exit 0
fi

# Increment iteration
NEW_ITERATION=$((ITERATION + 1))
jq ".iteration = $NEW_ITERATION" "$RALPH_STATE_FILE" > "$RALPH_STATE_FILE.tmp" && mv "$RALPH_STATE_FILE.tmp" "$RALPH_STATE_FILE"

log "Continuing loop, iteration $NEW_ITERATION"

# Block exit and re-inject prompt
echo "RALPH: Iteration $NEW_ITERATION/$MAX_ITERATIONS - Completion promise not found, continuing..."
echo ""
echo "Continue working on: $ORIGINAL_PROMPT"
echo ""
echo "When complete, output: <promise>$COMPLETION_PROMISE</promise>"

# Exit code 2 tells Claude Code to continue with the re-injected prompt
exit 2
