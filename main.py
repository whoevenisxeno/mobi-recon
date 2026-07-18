#!/usr/bin/env python3
"""Mobi Recon entrypoint. Numbered-menu TUI for network + Bluetooth recon on Termux."""
from __future__ import annotations

import sys
import threading
import time

from mobirecon import capabilities, config, ui
from mobirecon.modules import (
    arp,
    bluetooth,
    device,
    dns_whois_trace,
    export,
    host_discovery,
    known_devices,
    network_info,
    os_fingerprint,
    port_scan,
    watch,
    wifi,
)

caps = None  # populated in main()


# --------------------------------------------------------------------------
# Network menu actions
# --------------------------------------------------------------------------

def action_connection_info() -> None:
    with ui.console.status("Gathering connection info..."):
        info = network_info.get_connection_info()
    ui.render_kv_panel("Connection Info", {k: v for k, v in info.to_dict().items() if k != "errors"})
    for err in info.errors or []:
        ui.print_warning(err)
    if ui.confirm("Export this result?", default=False):
        j, t = export.export_result("connection_info", info)
        ui.print_success(f"Saved to {j} and {t}")


def action_host_discovery() -> None:
    cidr = ui.ask("Subnet to scan (CIDR)", default=_guess_cidr())
    with ui.console.status(f"Discovering hosts on {cidr}..."):
        hosts, method = host_discovery.discover_hosts(cidr)
    ui.print_info(f"Method used: {method}")
    ui.render_table(f"Hosts on {cidr}", hosts, columns=["ip", "mac", "vendor", "hostname", "response_time_ms"])
    if hosts:
        macs = [h.mac for h in hosts if h.mac]
        known_macs, unknown_macs = known_devices.classify(macs)
        if unknown_macs:
            ui.print_warning(f"{len(unknown_macs)} unknown device(s): {', '.join(unknown_macs)}")
    if ui.confirm("Export this result?", default=False):
        j, t = export.export_result("host_discovery", hosts)
        ui.print_success(f"Saved to {j} and {t}")


def _guess_cidr() -> str:
    info = network_info.get_connection_info(include_public=False)
    return info.subnet_cidr or "192.168.1.0/24"


def action_port_scan() -> None:
    host = ui.ask("Target host/IP")
    cfg = config.get_config()
    spec = ui.ask("Port spec (top-ports / full / e.g. 1-1000)", default=cfg.get("default_port_range", "1-1000"))
    do_service = ui.confirm("Attempt service/version detection?", default=False)
    with ui.console.status(f"Scanning {host}..."):
        results, method = port_scan.scan_ports(host, spec, service_detect=do_service)
    ui.print_info(f"Method used: {method}")
    ui.render_table(f"Open ports on {host}", results, columns=["port", "protocol", "state", "service", "product", "version", "banner"])
    if ui.confirm("Export this result?", default=False):
        j, t = export.export_result(f"port_scan_{host}", results)
        ui.print_success(f"Saved to {j} and {t}")


def action_os_fingerprint() -> None:
    host = ui.ask("Target host/IP")
    with ui.console.status(f"Fingerprinting {host}..."):
        guesses, err = os_fingerprint.fingerprint_os(host)
    if err:
        ui.print_error(err)
        return
    ui.render_table(f"OS guesses for {host}", guesses, columns=["name", "accuracy"])


def action_arp_table() -> None:
    with ui.console.status("Reading ARP/neighbor table..."):
        entries = arp.get_arp_table()
    ui.render_table("ARP / Neighbor Table", entries, columns=["ip", "mac", "vendor", "state"])
    if ui.confirm("Export this result?", default=False):
        j, t = export.export_result("arp_table", entries)
        ui.print_success(f"Saved to {j} and {t}")


def action_dns_whois_trace() -> None:
    target = ui.ask("Target host/IP/domain")
    sub = ui.ask("Action: [r]everse-dns / [w]hois / [t]raceroute", default="r").strip().lower()
    if sub.startswith("r"):
        with ui.console.status("Resolving..."):
            name = dns_whois_trace.reverse_dns(target)
        if name:
            ui.print_success(f"{target} -> {name}")
        else:
            ui.print_warning("No PTR record found (or lookup failed)")
    elif sub.startswith("w"):
        with ui.console.status("Querying whois..."):
            out, err = dns_whois_trace.whois_lookup(target)
        if err:
            ui.print_error(err)
        else:
            ui.console.print(out)
    elif sub.startswith("t"):
        with ui.console.status(f"Tracing route to {target} (this can take a while)..."):
            hops, err = dns_whois_trace.traceroute(target)
        if err:
            ui.print_error(err)
        else:
            ui.render_table(f"Traceroute to {target}", hops, columns=["hop", "address", "rtt_ms"])
    else:
        ui.print_error("Unknown action")


def network_menu() -> None:
    items = [
        ui.MenuItem("Connection info (local IP / gateway / SSID / public IP)", action_connection_info),
        ui.MenuItem(
            "Host discovery (subnet sweep)", action_host_discovery,
            enabled=caps.binaries.get("nmap") or caps.binaries.get("ping"),
            disabled_reason="needs nmap or ping",
        ),
        ui.MenuItem(
            "Port scan", action_port_scan,
            enabled=True,  # pure-Python socket fallback always available
        ),
        ui.MenuItem(
            "OS fingerprint (nmap -O)", action_os_fingerprint,
            enabled=caps.is_rooted and caps.binaries.get("nmap", False),
            disabled_reason="requires root",
        ),
        ui.MenuItem(
            "ARP / neighbor table", action_arp_table,
            enabled=caps.binaries.get("ip", False),
            disabled_reason="requires `ip` binary",
        ),
        ui.MenuItem(
            "Reverse DNS / whois / traceroute", action_dns_whois_trace,
            enabled=True,
        ),
    ]
    ui.show_menu("Network", items)


# --------------------------------------------------------------------------
# WiFi menu actions
# --------------------------------------------------------------------------

def action_wifi_scan() -> None:
    force = False
    remaining = wifi.cooldown_remaining()
    if remaining > 0:
        ui.print_warning(f"Scan cooldown: {remaining:.0f}s remaining (Android throttles to ~1/30s)")
        force = ui.confirm("Force a new scan anyway?", default=False)
    with ui.console.status("Scanning WiFi..."):
        aps, note = wifi.scan_access_points(force=force)
    ui.print_info(note)
    ui.render_table("Nearby Access Points", aps, columns=["ssid", "bssid", "vendor", "rssi", "frequency", "capabilities"])
    if aps and ui.confirm("Export this result?", default=False):
        j, t = export.export_result("wifi_scan", aps)
        ui.print_success(f"Saved to {j} and {t}")


def action_wifi_link_info() -> None:
    with ui.console.status("Reading current link info..."):
        data, err = wifi.get_connection_info()
    if err:
        ui.print_error(err)
        return
    ui.render_kv_panel("Current WiFi Link", data)


def wifi_menu() -> None:
    has_wifi_cli = caps.termux_clis.get("termux-wifi-scaninfo", False)
    reason = "" if caps.termux_api_app_responsive else "Termux:API app not responding"
    items = [
        ui.MenuItem(
            "Scan nearby access points", action_wifi_scan,
            enabled=has_wifi_cli and caps.termux_api_app_responsive,
            disabled_reason=reason or "needs termux-api",
        ),
        ui.MenuItem(
            "Current link info", action_wifi_link_info,
            enabled=caps.termux_clis.get("termux-wifi-connectioninfo", False) and caps.termux_api_app_responsive,
            disabled_reason=reason or "needs termux-api",
        ),
    ]
    ui.show_menu("WiFi", items)


# --------------------------------------------------------------------------
# Bluetooth menu actions
# --------------------------------------------------------------------------

def action_bluetooth_scan() -> None:
    backend, explanation = bluetooth.backend_status()
    ui.print_info(f"Backend: {backend} — {explanation}")
    if backend == "none":
        return
    with ui.console.status("Scanning Bluetooth (this can take ~15s)..."):
        devices, err = bluetooth.scan_devices()
    if err:
        ui.print_error(err)
        return
    ui.render_table("Bluetooth Devices", devices, columns=["name", "address", "vendor", "rssi", "kind"])
    if devices and ui.confirm("Export this result?", default=False):
        j, t = export.export_result("bluetooth_scan", devices)
        ui.print_success(f"Saved to {j} and {t}")


def action_bluetooth_status() -> None:
    backend, explanation = bluetooth.backend_status()
    ui.render_kv_panel("Bluetooth Backend", {"backend": backend, "detail": explanation})


def bluetooth_menu() -> None:
    backend, explanation = bluetooth.backend_status()
    items = [
        ui.MenuItem("Scan for devices", action_bluetooth_scan, enabled=backend != "none", disabled_reason=explanation),
        ui.MenuItem("Backend status", action_bluetooth_status),
    ]
    ui.show_menu("Bluetooth", items)


# --------------------------------------------------------------------------
# Device (own phone) menu actions
# --------------------------------------------------------------------------

def _device_action(title: str, fn) -> None:
    with ui.console.status(f"Fetching {title}..."):
        data, err = fn()
    if err:
        ui.print_error(err)
        return
    if isinstance(data, dict):
        ui.render_kv_panel(title, data)
    else:
        ui.console.print_json(data=data)


def device_menu() -> None:
    reason = "" if caps.termux_api_app_responsive else "Termux:API app not responding"
    items = [
        ui.MenuItem(
            "Telephony info", lambda: _device_action("Telephony Info", device.telephony_info),
            enabled=caps.termux_clis.get("termux-telephony-deviceinfo", False) and caps.termux_api_app_responsive,
            disabled_reason=reason or "needs termux-api",
        ),
        ui.MenuItem(
            "Sensor list", lambda: _device_action("Sensors", device.sensor_list),
            enabled=caps.termux_clis.get("termux-sensor", False) and caps.termux_api_app_responsive,
            disabled_reason=reason or "needs termux-api",
        ),
        ui.MenuItem(
            "Battery status", lambda: _device_action("Battery", device.battery_status),
            enabled=caps.termux_clis.get("termux-battery-status", False) and caps.termux_api_app_responsive,
            disabled_reason=reason or "needs termux-api",
        ),
        ui.MenuItem(
            "GPS location", lambda: _device_action("Location", device.location),
            enabled=caps.termux_clis.get("termux-location", False) and caps.termux_api_app_responsive,
            disabled_reason=reason or "needs termux-api",
        ),
    ]
    ui.show_menu("Device Info", items)


# --------------------------------------------------------------------------
# Known devices menu actions
# --------------------------------------------------------------------------

def action_list_known() -> None:
    known = known_devices.load_known()
    ui.render_table("Known Devices", list(known.values()), columns=["mac", "label", "vendor", "first_seen", "last_seen"])


def action_add_known() -> None:
    mac = ui.ask("MAC address")
    label = ui.ask("Label (e.g. 'my laptop')", default="")
    known_devices.add_known(mac, label)
    ui.print_success(f"Saved {mac} as '{label}'")


def action_remove_known() -> None:
    mac = ui.ask("MAC address to remove")
    if known_devices.remove_known(mac):
        ui.print_success("Removed")
    else:
        ui.print_warning("Not found")


def known_devices_menu() -> None:
    items = [
        ui.MenuItem("List known devices", action_list_known),
        ui.MenuItem("Add / label a device", action_add_known),
        ui.MenuItem("Remove a device", action_remove_known),
    ]
    ui.show_menu("Known Devices", items)


# --------------------------------------------------------------------------
# Watch mode
# --------------------------------------------------------------------------

def action_watch_mode() -> None:
    cidr = ui.ask("Subnet to watch (CIDR)", default=_guess_cidr())
    interval = int(ui.ask("Interval seconds", default="60"))
    ui.print_info("Watching... press Ctrl-C to stop.")

    stop_event = threading.Event()

    def stop_check() -> bool:
        return stop_event.is_set()

    try:
        for event in watch.watch_hosts(cidr, interval, stop_check):
            ts = event.timestamp
            ui.console.print(f"[dim]{ts}[/dim] — {event.total} hosts up (via {event.method})")
            for h in event.appeared:
                ui.print_success(f"appeared: {h.ip} {h.mac} {h.vendor}")
            for h in event.disappeared:
                ui.print_warning(f"disappeared: {h.ip} {h.mac} {h.vendor}")
    except KeyboardInterrupt:
        stop_event.set()
        ui.console.print()
        ui.print_info("Watch mode stopped.")


# --------------------------------------------------------------------------
# Settings / capability report
# --------------------------------------------------------------------------

def action_capability_report() -> None:
    global caps
    ui.render_kv_panel("Capability Probe", {
        "Termux environment": caps.is_termux,
        "Root": caps.is_rooted,
        "Termux:API app responsive": caps.termux_api_app_responsive,
        "Termux:API error": caps.termux_api_app_error or "-",
        "Bluetooth backend": caps.bluetooth_backend,
    })
    ui.render_table("Binaries", [{"name": k, "found": v} for k, v in caps.binaries.items()], columns=["name", "found"])
    ui.render_table("Termux:API commands", [{"name": k, "found": v} for k, v in caps.termux_clis.items()], columns=["name", "found"])
    if ui.confirm("Re-run probe?", default=False):
        caps = capabilities.get_capabilities(refresh=True)
        ui.print_success("Probe refreshed.")


def action_settings() -> None:
    cfg = config.get_config()
    ui.render_kv_panel("Current Config", cfg)
    if not ui.confirm("Edit a value?", default=False):
        return
    key = ui.ask("Key to edit", default="banner_text")
    if key not in cfg:
        ui.print_error(f"Unknown key: {key}")
        return
    current = cfg[key]
    new_val = ui.ask(f"New value for {key}", default=str(current))
    if isinstance(current, bool):
        cfg[key] = new_val.strip().lower() in ("1", "true", "yes", "on")
    elif isinstance(current, int):
        try:
            cfg[key] = int(new_val)
        except ValueError:
            ui.print_error("Expected an integer")
            return
    else:
        cfg[key] = new_val
    config.save_config(cfg)
    ui.print_success("Saved.")


def settings_menu() -> None:
    items = [
        ui.MenuItem("View / edit config", action_settings),
        ui.MenuItem("Capability report", action_capability_report),
    ]
    ui.show_menu("Settings", items)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> int:
    global caps
    ui.console.clear()
    ui.print_banner()

    with ui.console.status("Probing environment..."):
        caps = capabilities.get_capabilities()

    if not caps.is_termux:
        ui.print_warning("Not running inside Termux — some features (termux-* commands) will be unavailable.")
    if not caps.termux_api_app_responsive:
        ui.print_warning(f"Termux:API app check: {caps.termux_api_app_error}")

    top_items = [
        ui.MenuItem("Network", network_menu),
        ui.MenuItem("WiFi", wifi_menu),
        ui.MenuItem("Bluetooth", bluetooth_menu),
        ui.MenuItem("Device (this phone)", device_menu),
        ui.MenuItem("Known Devices", known_devices_menu),
        ui.MenuItem(
            "Watch Mode (diff subnet over time)", action_watch_mode,
            enabled=caps.binaries.get("nmap") or caps.binaries.get("ping"),
            disabled_reason="needs nmap or ping",
        ),
        ui.MenuItem("Settings / Capability Report", settings_menu),
    ]

    interrupted_once = False
    while True:
        explicit_exit = ui.show_menu("Mobi Recon — main menu", top_items, allow_back=False)
        if explicit_exit:
            break
        if interrupted_once:
            break
        interrupted_once = True
        ui.print_info("Press Ctrl-C again (or select 0) to exit.")

    ui.print_info("Goodbye.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        sys.exit(0)
