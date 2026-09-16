#!/usr/bin/env bash
# Claude Code statusline wrapper around `oh-my-posh claude`.
#
# The oh-my-posh claude segment only sees fields it has a struct for, and
# Claude Code's payload has no cumulative session token counts at all
# (context_window.total_* describe the *current context*, not the session).
# This wrapper derives the missing numbers and hands them to the template as
# environment variables (read there as {{ .Env.CLAUDE_OMP_* }}):
#
#   CLAUDE_OMP_REQS          API requests this session (main + subagents)
#   CLAUDE_OMP_IN            cumulative input processed (uncached + cache write + cache read)
#   CLAUDE_OMP_OUT           cumulative output tokens
#   CLAUDE_OMP_CACHE_R/_W    cumulative cache read / cache write tokens
#   CLAUDE_OMP_HIT           cache hit ratio % (payload prompt_cache.hit_ratio, else from transcript)
#   CLAUDE_OMP_MISSES        prompt-cache misses (payload prompt_cache.misses; empty if absent)
#   CLAUDE_OMP_COLD_AT       local HH:MM when the cached prefix expires (empty if unknown)
#   CLAUDE_OMP_BURN          estimated USD per wall-clock hour (empty in the first minute)
#
# If jq or the transcript is unavailable the variables are simply empty and
# the template hides those parts.

payload=$(cat)
config="${HOME}/.config/oh-my-posh/claude-omp.json"

if command -v jq >/dev/null 2>&1; then
  transcript=$(jq -r '.transcript_path // empty' <<<"$payload" 2>/dev/null)
  files=()
  if [[ -n "$transcript" && -f "$transcript" ]]; then
    files+=("$transcript")
    # Subagent transcripts live next to the main one and are billed too.
    for f in "${transcript%.jsonl}"/subagents/*.jsonl; do
      [[ -f "$f" ]] && files+=("$f")
    done
  fi

  vars=$(
    cat "${files[@]}" /dev/null 2>/dev/null |
      jq -nrR --argjson p "$payload" '
        def h: if . >= 1000000 then "\((. / 100000 | floor) / 10)M"
               elif . >= 1000 then "\((. / 100 | floor) / 10)K"
               else tostring end
             | sub("^(?<n>[0-9]+)(?<u>[KM])$"; "\(.n).0\(.u)");

        # One API response is split across several transcript lines that
        # repeat the same usage block, so dedupe by message id.
        (reduce (inputs | fromjson? | select(.type? == "assistant") | .message | select(.usage? and .id?))
           as $m ({}; .[$m.id] = $m.usage)) as $by_id
        | [$by_id[]] as $u
        | ($u | map(.input_tokens // 0) | add // 0) as $in
        | ($u | map(.cache_creation_input_tokens // 0) | add // 0) as $cw
        | ($u | map(.cache_read_input_tokens // 0) | add // 0) as $cr
        | ($u | map(.output_tokens // 0) | add // 0) as $out
        | ($in + $cw + $cr) as $all
        | ($p.prompt_cache // {}) as $pc
        | ($p.cost.total_duration_ms // 0) as $dur
        | [
            "CLAUDE_OMP_REQS=\($u | length)",
            "CLAUDE_OMP_IN=\(if $all > 0 then ($all | h) else "" end)",
            "CLAUDE_OMP_OUT=\(if $all > 0 then ($out | h) else "" end)",
            "CLAUDE_OMP_CACHE_R=\(if $all > 0 then ($cr | h) else "" end)",
            "CLAUDE_OMP_CACHE_W=\(if $all > 0 then ($cw | h) else "" end)",
            "CLAUDE_OMP_HIT=\(
              if $pc.hit_ratio != null then ($pc.hit_ratio * 100 | round | tostring)
              elif $all > 0 then ($cr * 100 / $all | round | tostring)
              else "" end)",
            "CLAUDE_OMP_MISSES=\($pc.misses // "")",
            "CLAUDE_OMP_COLD_AT=\(if $pc.expires_at then ($pc.expires_at | strflocaltime("%H:%M")) else "" end)",
            "CLAUDE_OMP_BURN=\(
              if $dur >= 60000 and ($p.cost.total_cost_usd // 0) > 0
              then ($p.cost.total_cost_usd / ($dur / 3600000) * 100 | round / 100
                    | tostring | sub("^(?<i>[0-9]+)$"; "\(.i).00") | sub("\\.(?<d>[0-9])$"; ".\(.d)0"))
              else "" end)"
          ][]
      ' 2>/dev/null
  )

  while IFS='=' read -r key value; do
    [[ "$key" == CLAUDE_OMP_* ]] && export "$key=$value"
  done <<<"$vars"
fi

printf '%s' "$payload" | oh-my-posh claude --config "$config"
