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

create_desktop_session() {
  local profile="$1"
  curl -fsS -X POST http://localhost:8000/api/v1/sessions \
    -H 'X-User-Id: smoke-user' \
    -H 'content-type: application/json' \
    -d "{
      \"session_kind\": \"desktop\",
      \"desktop_profile\": \"${profile}\",
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

verify_runtime() {
  local runtime_kind="$1"
  local runtime_name="$2"
  local create_response
  local session_id
  local session_state
  local clipboard_response
  local upload_response
  local downloads_response
  local screenshot_headers

  printf 'launching %s smoke session...\n' "${runtime_name}"
  if [[ "${runtime_kind}" == "browser" ]]; then
    create_response="$(create_session "${runtime_name}")"
  else
    create_response="$(create_desktop_session "${runtime_name}")"
  fi
  session_id="$(printf '%s' "${create_response}" | extract_json_field session_id)"
  printf '%s create response: %s\n' "${runtime_name}" "${create_response}"

  session_state=''
  for _ in $(seq 1 30); do
    sleep 2
    session_state="$(curl -fsS -H 'X-User-Id: smoke-user' "http://localhost:8000/api/v1/sessions/${session_id}")"
    if printf '%s' "${session_state}" | python -c "import json,sys; raise SystemExit(0 if json.load(sys.stdin)['status'] == 'active' else 1)"; then
      break
    fi
  done
  printf '%s state: %s\n' "${runtime_name}" "${session_state}"

  if ! printf '%s' "${session_state}" | python -c "import json,sys; assert json.load(sys.stdin)['status'] == 'active'"; then
    printf '%s worker did not become active\n' "${runtime_name}" >&2
    exit 1
  fi

  clipboard_response="$(curl -fsS -X POST "http://localhost:8000/api/v1/sessions/${session_id}/clipboard" \
    -H 'X-User-Id: smoke-user' \
    -H 'content-type: application/json' \
    -d '{"text":"smoke clipboard"}')"
  printf '%s clipboard: %s\n' "${runtime_name}" "${clipboard_response}"

  upload_response="$(upload_file "${session_id}")"
  printf '%s upload: %s\n' "${runtime_name}" "${upload_response}"

  downloads_response="$(curl -fsS -H 'X-User-Id: smoke-user' "http://localhost:8000/api/v1/sessions/${session_id}/downloads")"
  printf '%s downloads: %s\n' "${runtime_name}" "${downloads_response}"
  if ! printf '%s' "${downloads_response}" | python -c "import json,sys; items=json.load(sys.stdin)['items']; assert items and items[0]['filename']"; then
    printf '%s downloads are missing uploaded file\n' "${runtime_name}" >&2
    exit 1
  fi

  curl -fsS -H 'X-User-Id: smoke-user' "http://localhost:8000/api/v1/sessions/${session_id}/downloads/$(printf '%s' "${downloads_response}" | python -c "import json,sys; print(json.load(sys.stdin)['items'][0]['filename'])")" >/dev/null

  screenshot_headers="$(mktemp)"
  curl -fsS -D "${screenshot_headers}" -o /dev/null -H 'X-User-Id: smoke-user' "http://localhost:8000/api/v1/sessions/${session_id}/screenshot"
  if ! grep -qi '^content-type: image/png' "${screenshot_headers}"; then
    printf '%s screenshot did not return PNG\n' "${runtime_name}" >&2
    rm -f "${screenshot_headers}"
    exit 1
  fi
  rm -f "${screenshot_headers}"

  curl -fsS -X DELETE -H 'X-User-Id: smoke-user' "http://localhost:8000/api/v1/sessions/${session_id}" >/dev/null
}

for browser in chromium firefox; do
  verify_runtime browser "${browser}"
done

for profile in ubuntu-xfce kali-xfce; do
  verify_runtime desktop "${profile}"
done
