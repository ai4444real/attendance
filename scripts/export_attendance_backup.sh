#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_BACKUP_ROOT="${PROJECT_ROOT}/backups/attendance"
BACKUP_ROOT="${1:-${DEFAULT_BACKUP_ROOT}}"
TIMESTAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
OUTPUT_DIR="${BACKUP_ROOT}/${TIMESTAMP}"

TABLES=(
  "attendance_import_batches"
  "attendance_lessons"
  "attendance_lesson_participants"
  "attendance_review_actions"
  "attendance_lesson_source_segments"
  "attendance_identity_aliases"
  "attendance_courses"
  "attendance_instructors"
)

load_database_url() {
  if [[ -n "${DATABASE_URL:-}" ]]; then
    return
  fi

  local env_file="${PROJECT_ROOT}/.env"
  if [[ ! -f "${env_file}" ]]; then
    return
  fi

  local line
  line="$(grep -E '^DATABASE_URL=' "${env_file}" | tail -n 1 || true)"
  if [[ -z "${line}" ]]; then
    return
  fi

  DATABASE_URL="${line#DATABASE_URL=}"
  DATABASE_URL="${DATABASE_URL%\"}"
  DATABASE_URL="${DATABASE_URL#\"}"
  DATABASE_URL="${DATABASE_URL%\'}"
  DATABASE_URL="${DATABASE_URL#\'}"
  export DATABASE_URL
}

order_clause_for_table() {
  local table="$1"
  case "${table}" in
    attendance_courses)
      printf 'course_name'
      ;;
    *)
      printf 'id'
      ;;
  esac
}

require_command() {
  local command_name="$1"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "[backup] missing command: ${command_name}" >&2
    exit 1
  fi
}

load_database_url
require_command psql

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "[backup] DATABASE_URL is not configured." >&2
  echo "[backup] Export DATABASE_URL or add it to ${PROJECT_ROOT}/.env." >&2
  exit 1
fi

mkdir -p "${OUTPUT_DIR}"

MANIFEST="${OUTPUT_DIR}/manifest.txt"
{
  echo "created_at_utc=${TIMESTAMP}"
  echo "host=$(hostname)"
  echo "project_root=${PROJECT_ROOT}"
  echo "git_commit=$(git -C "${PROJECT_ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "database_url_configured=yes"
  echo
  echo "tables:"
} > "${MANIFEST}"

echo "[backup] output: ${OUTPUT_DIR}"

for table in "${TABLES[@]}"; do
  output_file="${OUTPUT_DIR}/${table}.csv"
  order_by="$(order_clause_for_table "${table}")"

  echo "[backup] exporting ${table}"
  psql "${DATABASE_URL}" \
    -v ON_ERROR_STOP=1 \
    -c "COPY (SELECT * FROM ${table} ORDER BY ${order_by}) TO STDOUT WITH (FORMAT csv, HEADER true, FORCE_QUOTE *);" \
    > "${output_file}"

  row_count="$(
    psql "${DATABASE_URL}" \
      -v ON_ERROR_STOP=1 \
      -At \
      -c "SELECT count(*) FROM ${table};"
  )"
  echo "- ${table}: ${row_count} rows -> ${table}.csv" >> "${MANIFEST}"
done

if command -v sha256sum >/dev/null 2>&1; then
  (
    cd "${OUTPUT_DIR}"
    sha256sum ./*.csv > SHA256SUMS
  )
  echo "[backup] checksums: ${OUTPUT_DIR}/SHA256SUMS"
fi

echo "[backup] manifest: ${MANIFEST}"
echo "[backup] done"
