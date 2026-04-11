#!/usr/bin/env bash
set -euo pipefail

frontend_health="$(curl -fsS http://localhost:3000/healthz)"
api_health="$(curl -fsS http://localhost:8000/healthz)"
rtc_config="$(curl -fsS http://localhost:8000/api/v1/rtc/config)"

printf 'frontend: %s\n' "${frontend_health}"
printf 'api: %s\n' "${api_health}"
printf 'rtc: %s\n' "${rtc_config}"

create_session() {
  local browser="$1"
  curl -fsS -X POST http://localhost:8000/api/v1/sessions \
    -H 'X-User-Id: smoke-user' \
    -H 'content-type: application/json' \
    -d "{
      \"browser\": \"${browser}\",
      \"resolution\": { \"width\": 1280, \"height\": 720 },
      \"timeout_seconds\": 120,
      \"idle_timeout_seconds\": 60,
      \"allow_file_upload\": true
    }"
}

extract_json_field() {
  local field="$1"
  python -c "import json,sys; print(json.load(sys.stdin)['${field}'])"
}

upload_file() {
  local session_id="$1"
  local temp_file
  temp_file="$(mktemp)"
  printf 'browserlab upload smoke' >"${temp_file}"
  curl -fsS -X POST "http://localhost:8000/api/v1/sessions/${session_id}/file-upload" \
    -H 'X-User-Id: smoke-user' \
    -F "upload=@${temp_file};type=text/plain"
  rm -f "${temp_file}"
}

for browser in chromium firefox; do
  printf 'launching %s smoke session...\n' "${browser}"
  create_response="$(create_session "${browser}")"
  session_id="$(printf '%s' "${create_response}" | extract_json_field session_id)"
  printf '%s create response: %s\n' "${browser}" "${create_response}"

  sleep 6
  session_state="$(curl -fsS -H 'X-User-Id: smoke-user' "http://localhost:8000/api/v1/sessions/${session_id}")"
  printf '%s state: %s\n' "${browser}" "${session_state}"

  if ! printf '%s' "${session_state}" | python -c "import json,sys; assert json.load(sys.stdin)['status'] == 'active'"; then
    printf '%s worker did not become active\n' "${browser}" >&2
    exit 1
  fi

  clipboard_response="$(curl -fsS -X POST "http://localhost:8000/api/v1/sessions/${session_id}/clipboard" \
    -H 'X-User-Id: smoke-user' \
    -H 'content-type: application/json' \
    -d '{"text":"smoke clipboard"}')"
  printf '%s clipboard: %s\n' "${browser}" "${clipboard_response}"

  upload_response="$(upload_file "${session_id}")"
  printf '%s upload: %s\n' "${browser}" "${upload_response}"

  curl -fsS -X DELETE -H 'X-User-Id: smoke-user' "http://localhost:8000/api/v1/sessions/${session_id}" >/dev/null
done
