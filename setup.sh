#!/data/data/com.termux/files/usr/bin/bash
# netrecon installer — idempotent, beginner-proof, safe to re-run.
set -u

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}   $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERR]${NC}  $*"; }
step() { echo -e "\n${CYAN}==>${NC} $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || { err "Could not cd into $SCRIPT_DIR"; exit 1; }

step "Checking environment"
if [ -z "${PREFIX:-}" ] || [[ "$PREFIX" != *com.termux* ]]; then
    err "This does not look like a Termux environment (\$PREFIX=${PREFIX:-unset})."
    err "netrecon is built for Termux on Android. Aborting."
    exit 1
fi
ok "Running inside Termux ($PREFIX)"

if command -v termux-info >/dev/null 2>&1; then
    :
fi
warn "If you installed Termux from the Play Store, it is outdated and broken."
warn "Use the F-Droid build or the GitHub release instead: https://github.com/termux/termux-app"

step "Updating package lists"
if pkg update -y >/tmp/netrecon_pkg_update.log 2>&1; then
    ok "Package lists updated"
else
    warn "pkg update reported issues — continuing anyway (see /tmp/netrecon_pkg_update.log)"
fi

step "Installing required packages"
PACKAGES="python nmap termux-api iproute2 whois dnsutils git"
FAILED_PACKAGES=""
for pkg_name in $PACKAGES; do
    if pkg list-installed 2>/dev/null | grep -q "^${pkg_name}/"; then
        ok "$pkg_name already installed"
        continue
    fi
    echo "Installing $pkg_name..."
    if pkg install -y "$pkg_name" >/tmp/netrecon_pkg_install.log 2>&1; then
        ok "$pkg_name installed"
    else
        warn "$pkg_name failed to install — the feature(s) it provides will be disabled."
        warn "  (see /tmp/netrecon_pkg_install.log for details)"
        FAILED_PACKAGES="$FAILED_PACKAGES $pkg_name"
    fi
done

if [ -n "$FAILED_PACKAGES" ]; then
    warn "Packages that failed to install:$FAILED_PACKAGES"
    warn "This is not fatal — netrecon degrades gracefully when a binary is missing."
fi

step "Installing Python dependencies"
if [ -f requirements.txt ]; then
    if pip install -r requirements.txt >/tmp/netrecon_pip.log 2>&1; then
        ok "Python dependencies installed"
    else
        warn "First pip install attempt failed — retrying with visible output..."
        if pip install -r requirements.txt; then
            ok "Python dependencies installed on retry"
        else
            err "pip install failed twice. Check the output above and your network connection."
            err "You can retry manually with: pip install -r requirements.txt"
        fi
    fi
else
    err "requirements.txt not found in $SCRIPT_DIR — skipping pip install"
fi

step "Checking Termux storage access"
if [ -d "$HOME/storage" ] && [ "$(ls -A "$HOME/storage" 2>/dev/null)" ]; then
    ok "Termux storage already set up"
else
    warn "Requesting storage access (a permission prompt should appear)..."
    termux-setup-storage
    sleep 1
    if [ -d "$HOME/storage" ]; then
        ok "Storage access configured"
    else
        warn "Storage access not confirmed — this only affects saving exports outside the app dir, not core features"
    fi
fi

step "Testing the Termux:API companion app"
TERMUX_API_OK=0
if ! command -v termux-wifi-connectioninfo >/dev/null 2>&1; then
    warn "termux-wifi-connectioninfo not found — termux-api package did not install correctly"
else
    API_TEST_OUTPUT=$(timeout 6 termux-wifi-connectioninfo 2>/tmp/netrecon_api_test.log)
    API_TEST_STATUS=$?
    if [ "$API_TEST_STATUS" -eq 124 ]; then
        err "Termux:API app did not respond (timed out after 6s)."
        err "This almost always means one of:"
        err "  1) The Termux:API app is not installed at all, or"
        err "  2) It was installed from a DIFFERENT source than Termux itself"
        err "     (e.g. Termux from F-Droid + Termux:API from Play Store — signatures"
        err "     must match, or the app link silently fails and calls hang forever)."
        err "FIX: install Termux:API from the EXACT SAME source as your Termux app:"
        err "  F-Droid: https://f-droid.org/packages/com.termux.api/"
        err "  GitHub:  https://github.com/termux/termux-api/releases"
        err "Then re-run this script."
    elif [ -n "$API_TEST_OUTPUT" ]; then
        ok "Termux:API app responded"
        TERMUX_API_OK=1
    else
        warn "termux-wifi-connectioninfo produced no output (see /tmp/netrecon_api_test.log)"
        warn "WiFi/Bluetooth/device-info features may not work until the Termux:API app is installed"
    fi
fi

step "Checking root access"
IS_ROOTED=0
if command -v su >/dev/null 2>&1; then
    ok "su binary found — this device may be rooted"
    IS_ROOTED=1
    echo "  To enable OS fingerprinting and BlueZ-based Bluetooth scanning, install BlueZ:"
    echo "    pkg install bluez"
else
    warn "No root detected. This is fine — netrecon works fully on stock non-rooted Termux."
    warn "Bluetooth discovery and OS fingerprinting will stay disabled (need root); everything"
    warn "else (network scanning, WiFi, ARP, device info) still works."
fi

step "Installing launcher"
LAUNCHER="$PREFIX/bin/netrecon"
cat > "$LAUNCHER" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
exec python "$SCRIPT_DIR/main.py" "\$@"
EOF
chmod +x "$LAUNCHER"
ok "Launcher installed at $LAUNCHER"

step "Creating output/log directories"
mkdir -p "$SCRIPT_DIR/output" "$SCRIPT_DIR/logs"
ok "Ready: $SCRIPT_DIR/output and $SCRIPT_DIR/logs"

echo
echo -e "${CYAN}================= Setup complete =================${NC}"
echo -e "Launch netrecon with:  ${GREEN}netrecon${NC}"
echo -e "  (or: python $SCRIPT_DIR/main.py)"
echo
if [ "$TERMUX_API_OK" -eq 0 ]; then
    warn "Termux:API app is not confirmed working — WiFi/device-info features will show as disabled."
fi
warn "REMINDER: Android Location must be ON or WiFi scans will silently return empty results."
if [ "$IS_ROOTED" -eq 0 ]; then
    warn "REMINDER: No root detected — Bluetooth discovery and OS fingerprinting stay disabled."
fi
echo
