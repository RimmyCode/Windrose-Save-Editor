#!/usr/bin/env bash
# Build a distributable zip of the Windrose Save Editor.
# Usage: ./scripts/build-release.sh [output_dir] [archive_name]

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Pull version from the package so archive name is always in sync
version="$(python3 -c "import sys; sys.path.insert(0, '${repo_root}'); from windrose_save_editor import __version__; print(__version__)")"

output_dir="${1:-"${repo_root}/dist"}"
archive_name="${2:-"windrose-save-editor-${version}.zip"}"
staging_dir="${output_dir}/package"
archive_path="${output_dir}/${archive_name}"

echo "Building Windrose Save Editor ${version}..."

rm -rf "${staging_dir}"
mkdir -p "${staging_dir}/OPTIONAL"

# ── Package (exclude __pycache__) ────────────────────────────────────────────
rsync -a --exclude="__pycache__" --exclude="*.pyc" \
  "${repo_root}/windrose_save_editor/" \
  "${staging_dir}/windrose_save_editor/"

# ── Thin launcher — keeps the same entry-point filename users already know ───
cat > "${staging_dir}/Windrose Save Editor.py" << 'LAUNCHER'
#!/usr/bin/env python3
from windrose_save_editor.cli import main
if __name__ == "__main__":
    main()
LAUNCHER

# ── Static files (skip silently if a file was removed in this version) ───────
static_files=(
  "Item ID Database.html"
  "README.md"
  "GUIDE.md"
  "rocksdb.dll"
  "librocksdb.so"
)

for f in "${static_files[@]}"; do
  [[ -f "${repo_root}/${f}" ]] && cp "${repo_root}/${f}" "${staging_dir}/${f}"
done

# ── OPTIONAL extras ───────────────────────────────────────────────────────────
optional_files=(
  "OPTIONAL/fmodel_export.txt"
  "OPTIONAL/IGNORE.html"
  "OPTIONAL/parse_items.py"
)

for f in "${optional_files[@]}"; do
  [[ -f "${repo_root}/${f}" ]] && cp "${repo_root}/${f}" "${staging_dir}/${f}"
done

# ── Zip ───────────────────────────────────────────────────────────────────────
rm -f "${archive_path}"
(cd "${staging_dir}" && zip -r -X "../${archive_name}" .)

echo "Created ${archive_path}"
