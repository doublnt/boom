#!/bin/bash
set -eo pipefail

INSTALL_DIR="${BOOM_INSTALL_DIR:-$HOME/.local/bin}"

if ! mkdir -p "$INSTALL_DIR"; then
  echo "Error: cannot create $INSTALL_DIR" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/boom" "$INSTALL_DIR/boom"
chmod 755 "$INSTALL_DIR/boom"

echo "Installed: $INSTALL_DIR/boom"

case ":$PATH:" in
  *":$INSTALL_DIR:"*)
    ;;
  *)
    echo ""
    echo "Note: $INSTALL_DIR is not in your PATH."
    echo "Add this to your shell profile:"
    echo "  export PATH=\"$INSTALL_DIR:\$PATH\""
    ;;
esac
