# --- Prompt (Oh My Posh) -------------------------------------
if command -v oh-my-posh >/dev/null 2>&1; then
  OMP_THEME="$HOME/.config/oh-my-posh/system-omp.json"
  if [ -f "$OMP_THEME" ]; then
    eval "$(oh-my-posh init zsh --config "$OMP_THEME")"
  else
    eval "$(oh-my-posh init zsh)"
  fi
fi
