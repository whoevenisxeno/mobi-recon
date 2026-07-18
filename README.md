# netrecon

A network + Bluetooth **reconnaissance** TUI for Termux on Android. Discovery
and enumeration only — no attacks, no exploits, no deauth, no cracking, no
injection. Built for scanning networks and devices you own or are authorized
to test.

Runs on a stock, **non-rooted** Termux install. Extra features (OS
fingerprinting, BlueZ Bluetooth scanning) unlock automatically when root is
available. Every feature is gated by a runtime capability probe — nothing
crashes or fakes output when a dependency is missing; the menu just tells you
why an item is disabled.

## Quickstart

```bash
pkg install git -y
git clone <this-repo-url> netrecon
cd netrecon
bash setup.sh
netrecon
```

`setup.sh` is idempotent — re-run it any time (e.g. after a Termux update) and
it will only do what's still needed.

## Feature matrix

| Feature | Stock Termux | Needs Termux:API | Needs root |
|---|:---:|:---:|:---:|
| Connection info (local IP, gateway, subnet) | ✅ | | |
| Public IP + geolocation | ✅ (needs internet) | | |
| SSID of current network | | ✅ | |
| Host discovery (subnet sweep) | ✅ (ping sweep fallback) | | improves with nmap |
| Port scan (connect scan) | ✅ (socket fallback) | | |
| Port scan (SYN scan) | | | ✅ |
| Service/version detection + banner grab | ✅ (banner grab always works) | | improves with nmap -sV |
| OS fingerprinting (nmap -O) | | | ✅ |
| ARP / neighbor table | ✅ | | |
| Reverse DNS | ✅ | | |
| whois | ✅ (needs `whois` package) | | |
| traceroute | ✅ (needs `traceroute` package) | | |
| WiFi AP scan | | ✅ (+ Location ON) | |
| WiFi current link info | | ✅ | |
| Bluetooth scan | | | ✅ (BlueZ) or unofficial Termux fork |
| Device info (telephony/sensors/battery/GPS) | | ✅ | |
| Known-devices tracking | ✅ | | |
| Watch mode (diff over time) | ✅ | | |
| Export to JSON/TXT | ✅ | | |

## Limitations (read this before filing a bug)

- **Android throttles WiFi scans** to roughly once per 30 seconds, and returns
  an **empty list** if Location services are off — this is Android policy,
  not a netrecon bug. The tool shows a cooldown timer and an explicit message
  instead of a silent empty table.
- **Bluetooth has no official Termux:API scan command.** netrecon looks for a
  backend in this order: BlueZ (`bluetoothctl`/`hcitool`, usually needs root)
  → the unofficial Termux fork's `termux-bluetooth-scaninfo` → otherwise it
  reports plainly that no backend is available. It will never fabricate or
  simulate a scan result.
- **The Termux:API *app* is a separate APK from the `termux-api` package.**
  The CLI shims (`termux-wifi-scaninfo`, etc.) install fine even when the app
  itself is missing — calling them then just hangs. `setup.sh` actively tests
  this with a timeout and prints exact fix instructions if it fails. The app
  must come from the **same source** as Termux itself (both F-Droid, or both
  GitHub) — mixed signatures fail silently.
- **OS fingerprinting and SYN scans need root** (raw socket access). On
  non-rooted devices these menu items are visibly disabled with the reason
  shown, not hidden.
- The bundled OUI (MAC vendor) database is a curated subset of common vendors,
  not the full IEEE registry. Enable `online_vendor_lookup` in the config to
  fall back to an online API for unknown prefixes (disabled by default —
  sends the MAC prefix to a third party).

## Configuration

`config.json` is created on first run (see `netrecon/config.py` for defaults).
Editable in-app via **Settings → View / edit config**, or by hand:

```json
{
  "banner_text": "NETRECON",
  "banner_font": "slant",
  "color_theme": "cyan",
  "default_port_range": "1-1000",
  "scan_timeout": 15,
  "online_vendor_lookup": false,
  "wifi_scan_cooldown_seconds": 30
}
```

## Output

- Scan results export to `./output/<name>_<timestamp>.{json,txt}`.
- All activity is logged to `./logs/netrecon_<date>.log`.
- Known devices persist in `known_devices.json` in the repo root.

## Screenshots

_placeholder — add screenshots of the main menu, host discovery, and capability report here._

## Project layout

```
main.py                 entrypoint / menu wiring
netrecon/
  capabilities.py        runtime capability probe (the backbone)
  utils.py                subprocess wrapper (timeouts, logging) — all external
                           commands go through this
  config.py               JSON config load/save
  oui.py                  MAC vendor lookup (offline DB + optional online fallback)
  ui.py                    rich/pyfiglet menu + rendering helpers
  modules/                 one file per feature area
data/oui.tsv              bundled offline OUI database
setup.sh                  beginner-proof installer
```

## License

MIT — see [LICENSE](LICENSE).
