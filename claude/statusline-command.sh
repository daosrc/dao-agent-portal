#!/bin/sh
input=$(cat)
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // empty')
model=$(echo "$input" | jq -r '.model.display_name // empty')
used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')

# Git branch (skip optional locks)
branch=""
if [ -n "$cwd" ]; then
  branch=$(GIT_OPTIONAL_LOCKS=0 git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null)
fi

# Directory: replace $HOME with ~
home="$HOME"
display_dir="${cwd/#$home/\~}"

# Build output
line=""

# Dir segment
printf "\033[34m%s\033[0m" "$display_dir"

# Git branch segment
if [ -n "$branch" ]; then
  printf " \033[32mgit:(%s)\033[0m" "$branch"
fi

# Model segment
if [ -n "$model" ]; then
  printf " \033[35m[%s]\033[0m" "$model"
fi

# Context usage segment
if [ -n "$used" ]; then
  printf " \033[33mctx:%.0f%%\033[0m" "$used"
fi

echo ""
