#!/usr/bin/env bash
# Test procd arguments without touching a device, filesystem, or daemon.
set -euo pipefail
record=()
fixture_enabled=1
config_load() { :; }
config_get_bool() {
  local value="${4:-1}"
  [ "$3" != enabled ] || value="$fixture_enabled"
  printf -v "$1" '%s' "$value"
}
config_get() {
  local value="${4:-}"
  [ "$3" != listen ] || value='0.0.0.0:12023'
  printf -v "$1" '%s' "$value"
}
# The only executable check is the known package binary; do not run it.
fixture_test() {
  if [[ "${1:-}" == -x && "${2:-}" == /usr/bin/daed ]]; then return 0; fi
  builtin [ "$@"
}
shopt -s expand_aliases
alias '['='fixture_test'
mkdir() { :; }
chmod() { :; }
procd_open_instance() { :; }
procd_close_instance() { :; }
procd_set_param() {
  if [[ "$1" == command ]]; then shift; record=("$@"); fi
}
source PATCH/daed-pkg/daed/files/etc/init.d/daed
start_service
[[ "${record[*]}" == '/usr/bin/daed run -c /etc/daed-kdae -l 0.0.0.0:12023' ]]
fixture_enabled=0
record=()
start_service
[[ "${#record[@]}" == 0 ]]
echo 'PASS: Go procd command, independent data directory, retained listen option and disabled-service behavior; no Rust-only flags.'
