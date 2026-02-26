#!/usr/bin/env python3
"""
Import alert JSON files into Grafana via the Ruler API (non-provisioning, editable in UI)

Usage:
  python3 import_alerts.py [files...]          # default: dg5R_alert.json dg5W_alert.json
  python3 import_alerts.py dg5R_alert.json     # single file
  python3 import_alerts.py --delete-only       # delete all rules (no reimport)
  python3 import_alerts.py --delete            # delete then reimport
  python3 import_alerts.py [--host HOST] [--user USER] [--password PASS]
  python3 import_alerts.py [--host HOST] --token <API_TOKEN>
  python3 import_alerts.py --check-perms       # check current user permissions

Issuing an API token (if you get a 403 error):
  Grafana UI → Administration → Service Accounts → Add service account
  Role: Admin → Add token → copy the token and pass it via --token option

Default: http://localhost:3000  admin/deepgadget
"""

import json
import sys
import urllib.request
import urllib.error
import argparse
import base64
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DEFAULT_ALERT_FILES = [str(SCRIPT_DIR / "dg5R_alert.json"), str(SCRIPT_DIR / "dg5W_alert.json")]

def api(host, auth_header, method, path, body=None):
    url = f"{host}{path}"
    headers = {"Content-Type": "application/json", "Authorization": auth_header}
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"  HTTP {e.code}: {err[:300]}")
        return None

def make_auth(user, pw, token):
    if token:
        return f"Bearer {token}"
    cred = base64.b64encode(f"{user}:{pw}".encode()).decode()
    return f"Basic {cred}"

def ensure_folder(host, auth, title):
    folders = api(host, auth, "GET", "/api/folders") or []
    for f in folders:
        if f["title"] == title:
            print(f"  Folder '{title}' already exists: uid={f['uid']}")
            return f["uid"]
    result = api(host, auth, "POST", "/api/folders", {"title": title})
    if result:
        print(f"  Created folder '{title}': uid={result['uid']}")
        return result["uid"]
    return None

def get_folder_uid(host, auth, title):
    """Return existing folder UID or None (does not create)."""
    folders = api(host, auth, "GET", "/api/folders") or []
    for f in folders:
        if f["title"] == title:
            return f["uid"]
    return None

def interval_to_duration(s):
    """'1m' → '1m0s'"""
    s = s.strip()
    if s.endswith("m"):
        return s + "0s"
    return s

def get_prometheus_uid(host, auth):
    datasources = api(host, auth, "GET", "/api/datasources") or []
    for ds in datasources:
        if ds.get("type") == "prometheus":
            return ds["uid"]
    return None

def check_perms(host, auth):
    """Check accessible permissions with current credentials"""
    print("\n[Permission Check]")
    me = api(host, auth, "GET", "/api/user")
    if me:
        print(f"  User: {me.get('login')} / Role: {me.get('orgRole')} / isGrafanaAdmin: {me.get('isGrafanaAdmin')}")
    else:
        sa = api(host, auth, "GET", "/api/access-control/user/permissions?reloadcache=true")
        if sa is None:
            print("  Authentication failed - check host/token")
            return
        print("  Authenticated as Service Account token")

    perms = api(host, auth, "GET", "/api/access-control/user/permissions?reloadcache=true") or {}
    alert_perms = {k: v for k, v in perms.items() if "alert" in k.lower() or "folder" in k.lower()}
    if alert_perms:
        print("  Alert/Folder permissions:")
        for k, v in sorted(alert_perms.items()):
            print(f"    {k}: {v}")
    else:
        print("  No alert permissions found (→ Service Account Admin token required)")

def delete_folder_rules(host, auth, folder_uid):
    """Delete all alert rule groups in a folder."""
    existing = api(host, auth, "GET",
                   f"/api/ruler/grafana/api/v1/rules/{folder_uid}") or {}
    if not isinstance(existing, dict) or not existing:
        print("  No rules found.")
        return
    deleted = 0
    for group_name in list(existing.keys()):
        print(f"  DELETE group '{group_name}' ... ", end="", flush=True)
        result = api(host, auth, "DELETE",
                     f"/api/ruler/grafana/api/v1/rules/{folder_uid}/{group_name}")
        if result is not None:
            print("OK")
            deleted += 1
        else:
            print("FAILED")
    print(f"  Deleted {deleted} group(s)")

def delete_file(file_path, host, auth):
    """Delete all rules defined in an alert JSON file."""
    print(f"\n=== DELETE {file_path} ===")
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
    folder_title = data["groups"][0]["folder"]
    folder_uid = get_folder_uid(host, auth, folder_title)
    if not folder_uid:
        print(f"  Folder '{folder_title}' not found, nothing to delete.")
        return
    print(f"  Folder: '{folder_title}' (uid={folder_uid})")
    delete_folder_rules(host, auth, folder_uid)

def import_file(file_path, host, auth, dst_uid, delete=False):
    """Import a single alert JSON file into Grafana."""
    print(f"\n=== {file_path} ===")

    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    # Replace datasource UID if needed
    src_uid = data["groups"][0]["rules"][0]["data"][0]["datasourceUid"]
    if src_uid != dst_uid:
        print(f"[0] Replacing datasource UID: {src_uid} → {dst_uid}")
        data = json.loads(json.dumps(data).replace(f'"{src_uid}"', f'"{dst_uid}"'))
    else:
        print(f"[0] Datasource UID: {dst_uid} (no change)")

    folder_title = data["groups"][0]["folder"]
    print(f"[1] Folder: '{folder_title}'")
    folder_uid = ensure_folder(host, auth, folder_title)
    if not folder_uid:
        print("ERROR: Failed to create folder")
        return False

    if delete:
        print("[1.5] Deleting existing rules before reimport ...")
        delete_folder_rules(host, auth, folder_uid)

    # Collect existing rule UIDs (to distinguish new vs update)
    existing = api(host, auth, "GET",
                   f"/api/ruler/grafana/api/v1/rules/{folder_uid}") or {}
    existing_uids = set()
    if isinstance(existing, dict):
        for grp_list in existing.values():
            if isinstance(grp_list, list):
                for g in grp_list:
                    for r in g.get("rules", []):
                        uid = r.get("grafana_alert", {}).get("uid")
                        if uid:
                            existing_uids.add(uid)

    print(f"[2] Alert Rules import ({len(data['groups'])} groups)")
    for group in data["groups"]:
        group_name = group["name"]
        interval = interval_to_duration(group.get("interval", "1m"))

        rules = []
        for rule in group["rules"]:
            ga = {
                "title": rule["title"],
                "condition": rule["condition"],
                "data": rule["data"],
                "no_data_state": rule.get("noDataState", "NoData"),
                "exec_err_state": rule.get("execErrState", "Error"),
                "is_paused": rule.get("isPaused", False),
                "missing_series_evals_to_resolve": rule.get("missingSeriesEvalsToResolve", 1),
            }
            if rule["uid"] in existing_uids:
                ga["uid"] = rule["uid"]  # update existing rule
            ruler_rule = {
                "grafana_alert": ga,
                "keep_firing_for": rule.get("keepFiringFor", "0s"),
                "for": rule.get("for", "1m"),
                "labels": rule.get("labels", {}),
                "annotations": rule.get("annotations", {}),
            }
            rules.append(ruler_rule)

        body = {"name": group_name, "interval": interval, "rules": rules}

        print(f"  POST group '{group_name}' ({len(rules)} rules) ... ", end="", flush=True)
        result = api(host, auth, "POST",
                     f"/api/ruler/grafana/api/v1/rules/{folder_uid}", body)
        print("OK" if result is not None else "FAILED")

    print("[3] Verify result")
    result = api(host, auth, "GET",
                 f"/api/ruler/grafana/api/v1/rules/{folder_uid}") or {}
    count = sum(
        len(g.get("rules", []))
        for grp_list in result.values() if isinstance(grp_list, list)
        for g in grp_list
    ) if isinstance(result, dict) else 0
    print(f"  Rules registered in Grafana: {count}")
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", default=DEFAULT_ALERT_FILES,
                        help="Alert JSON files to import (default: dg5R_alert.json dg5W_alert.json)")
    parser.add_argument("--host", default="http://localhost:3000")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", default="deepgadget")
    parser.add_argument("--token", default=None, help="Grafana API token (use instead of --user/--password, recommended on 403 errors)")
    parser.add_argument("--datasource-uid", default=None, help="Prometheus datasource UID (auto-detected if not specified)")
    parser.add_argument("--delete", action="store_true", help="Delete existing rules then reimport")
    parser.add_argument("--delete-only", action="store_true", help="Delete all rules and exit (no reimport)")
    parser.add_argument("--check-perms", action="store_true", help="Check current user permissions and exit")
    args = parser.parse_args()

    host = args.host
    auth = make_auth(args.user, args.password, args.token)
    # Resolve relative paths against the script's directory
    files = [str(SCRIPT_DIR / f) if not Path(f).is_absolute() else f for f in args.files]

    if args.check_perms:
        check_perms(host, auth)
        return

    if args.delete_only:
        for file_path in files:
            delete_file(file_path, host, auth)
        return

    # Resolve datasource UID once for all files
    if args.datasource_uid:
        dst_uid = args.datasource_uid
    else:
        dst_uid = get_prometheus_uid(host, auth)
        if not dst_uid:
            print("ERROR: Prometheus datasource not found. Specify it manually with --datasource-uid.")
            sys.exit(1)

    for file_path in files:
        import_file(file_path, host, auth, dst_uid, delete=args.delete)

if __name__ == "__main__":
    main()
