#!/usr/bin/env bash

set -Eeuo pipefail

log_file="${1:-build.log}"

if [[ ! -f "$log_file" ]]; then
	echo "Build log not found: $log_file" >&2
	exit 1
fi

clean_log() {
	sed -E $'s/\x1B\\[[0-9;]*[[:alpha:]]//g; s/\r$//' "$log_file"
}

first_error_line="$(
	clean_log |
		awk '/(^|[[:space:]])(ERROR:|FAILED:|Error [0-9]+|错误 [0-9]+|fatal error:|undefined reference|No rule to make target|failed to build|recipe for target|go: .*requires go)|make\[[0-9]+\]: \*\*\*/ && !found { print NR; found = 1 }'
)"

echo "=== Build error summary ==="

if [[ -z "$first_error_line" ]]; then
	echo "No common error markers found in $log_file"
	echo "Last 80 log lines:"
	clean_log | tail -80
	exit 0
fi

echo "First matching error context around line $first_error_line:"
	start=$(( first_error_line > 25 ? first_error_line - 25 : 1 ))
	end=$(( first_error_line + 45 ))
	clean_log | sed -n "${start},${end}p"

echo
echo "Last matching error lines:"
clean_log |
	awk '/(^|[[:space:]])(ERROR:|FAILED:|Error [0-9]+|错误 [0-9]+|fatal error:|undefined reference|No rule to make target|failed to build|recipe for target|go: .*requires go)|make\[[0-9]+\]: \*\*\*/ { print NR ":" $0 }' |
	tail -20

# build.log 是 make 的静默输出，某些失败（例如 target/linux 的镜像组装）只会在
# OpenWrt 的按包日志里留下真正的报错，这里把 logs/ 里的证据也翻出来。
logs_dir="${2:-logs}"
if [[ -d "$logs_dir" ]]; then
	echo
	echo "=== Per-package logs under $logs_dir ==="
	matched=0
	while IFS= read -r f; do
		[[ -n "$f" ]] || continue
		matched=1
		echo "----- $f (last 40 lines) -----"
		tail -n 40 "$f" || true
	done < <(grep -rIl -E 'Error [0-9]+|ERROR:|FAILED|error:|No rule to make target' "$logs_dir" 2>/dev/null | head -20 || true)
	if [[ "$matched" -eq 0 ]]; then
		echo "no error markers found in $logs_dir"
		echo "--- newest files in $logs_dir ---"
		find "$logs_dir" -type f -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -15 | awk '{print $2}' || true
	fi
fi
