#!/usr/bin/env bash
# Build a standalone exe distribution of the Windrose Save Editor.
# Requires: pip install -e ".[build]"
# Usage: ./scripts/build-exe.sh [output_zip]

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

version=$(python -c "from windrose_save_editor import __version__; print(__version__)")
zip_name="${1:-"windrose-save-editor-${version}-exe.zip"}"
dist_app="${repo_root}/dist/Windrose Save Editor"
zip_path="${repo_root}/dist/${zip_name}"

echo "Building Windrose Save Editor ${version} (exe)..."

pyinstaller --clean windrose.spec

rm -f "${zip_path}"
(cd "${repo_root}/dist/Windrose Save Editor" && zip -r -X "../${zip_name}" *)

echo "Created ${zip_path}"
