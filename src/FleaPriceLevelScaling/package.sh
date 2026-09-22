#!/usr/bin/env bash
# Builds the mod in Release and zips it up as a ready-to-extract SPT_Runtime tree
# (SPT_Runtime/user/mods/FleaPriceLevelScaling/...), the same layout DrakiaXYZ's SPT mods use so a
# release can be extracted straight onto an SPT install.
set -euo pipefail

# Ensure dotnet in PATH on Windows Git Bash environments if not already present
export PATH="$PATH:/c/Program Files/dotnet"

cd "$(dirname "${BASH_SOURCE[0]}")"

MOD_NAME=FleaPriceLevelScaling
VERSION=$(sed -n 's/.*SemanticVersioning\.Version Version { get; init; } = new("\(.*\)").*/\1/p' FleaPriceLevelScalingMetadata.cs)
if [ -z "$VERSION" ]; then
    echo "could not read version from FleaPriceLevelScalingMetadata.cs" >&2
    exit 1
fi

echo "Packaging ${MOD_NAME} v${VERSION}"

dotnet build -c Release

PACKAGE_DIR=Package
STAGE_ROOT="${PACKAGE_DIR}/SPT_Runtime"
STAGE_DIR="${STAGE_ROOT}/user/mods/${MOD_NAME}"
ARCHIVE="${PACKAGE_DIR}/${MOD_NAME}-${VERSION}.zip"

rm -rf "${STAGE_ROOT}"
mkdir -p "${STAGE_DIR}"
cp -r "bin/Release/${MOD_NAME}/." "${STAGE_DIR}/"

rm -f "${ARCHIVE}"
(cd "${PACKAGE_DIR}" && zip -rq "$(basename "${ARCHIVE}")" SPT_Runtime)

echo "wrote ${ARCHIVE}"
