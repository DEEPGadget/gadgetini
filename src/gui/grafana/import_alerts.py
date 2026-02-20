#!/usr/bin/env python3
"""
dg5R_alert.json → Grafana Ruler API로 import (비-provisioning, UI 편집 가능)

Usage:
  python3 import_alerts.py [--host HOST] [--user USER] [--password PASS]
  python3 import_alerts.py [--host HOST] --token <API_TOKEN>
  python3 import_alerts.py --check-perms   # 현재 사용자 권한 확인

API 토큰 발급 (403 에러 시):
  Grafana UI → Administration → Service Accounts → Add service account
  Role: Admin → Add token → 토큰 복사 후 --token 옵션으로 사용

Default: http://localhost:3000  admin/admin
"""

import json
import sys
import urllib.request
import urllib.error
import argparse
import base64

ALERT_JSON = "dg5R_alert.json"

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
    """현재 인증 정보로 접근 가능한 권한 확인"""
    print("\n[권한 확인]")
    me = api(host, auth, "GET", "/api/user")
    if me:
        print(f"  User: {me.get('login')} / Role: {me.get('orgRole')} / isGrafanaAdmin: {me.get('isGrafanaAdmin')}")
    else:
        sa = api(host, auth, "GET", "/api/access-control/user/permissions?reloadcache=true")
        if sa is None:
            print("  인증 실패 - host/token 확인 필요")
            return
        print("  Service Account 토큰으로 인증됨")

    perms = api(host, auth, "GET", "/api/access-control/user/permissions?reloadcache=true") or {}
    alert_perms = {k: v for k, v in perms.items() if "alert" in k.lower() or "folder" in k.lower()}
    if alert_perms:
        print("  Alert/Folder 관련 권한:")
        for k, v in sorted(alert_perms.items()):
            print(f"    {k}: {v}")
    else:
        print("  Alert 관련 권한 없음 (→ Service Account Admin 토큰 필요)")

def replace_datasource_uid(rules, old_uid, new_uid):
    """rule data 안의 datasourceUid를 일괄 교체"""
    text = json.dumps(rules)
    text = text.replace(f'"{old_uid}"', f'"{new_uid}"')
    return json.loads(text)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="http://localhost:3000")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", default="admin")
    parser.add_argument("--token", default=None, help="Grafana API 토큰 (--user/--password 대신 사용, 403 에러 시 권장)")
    parser.add_argument("--datasource-uid", default=None, help="Prometheus datasource UID (미지정 시 자동 감지)")
    parser.add_argument("--delete", action="store_true", help="기존 rules 삭제 후 재import")
    parser.add_argument("--check-perms", action="store_true", help="현재 사용자 권한만 확인하고 종료")
    args = parser.parse_args()

    host = args.host
    auth = make_auth(args.user, args.password, args.token)

    if args.check_perms:
        check_perms(host, auth)
        return

    with open(ALERT_JSON, encoding="utf-8") as f:
        data = json.load(f)

    # Datasource UID 결정
    src_uid = data["groups"][0]["rules"][0]["data"][0]["datasourceUid"]
    if args.datasource_uid:
        dst_uid = args.datasource_uid
    else:
        dst_uid = get_prometheus_uid(host, auth)
        if not dst_uid:
            print("ERROR: Prometheus datasource를 찾을 수 없습니다. --datasource-uid로 직접 지정하세요.")
            sys.exit(1)
    if src_uid != dst_uid:
        print(f"\n[0] Datasource UID 교체: {src_uid} → {dst_uid}")
        data = json.loads(json.dumps(data).replace(f'"{src_uid}"', f'"{dst_uid}"'))
    else:
        print(f"\n[0] Datasource UID: {dst_uid} (변경 없음)")

    folder_title = data["groups"][0]["folder"]
    print(f"\n[1] Folder: '{folder_title}'")
    folder_uid = ensure_folder(host, auth, folder_title)
    if not folder_uid:
        print("ERROR: 폴더 생성 실패")
        sys.exit(1)

    # 기존에 등록된 rule UID 수집 (신규/업데이트 구분용)
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

    print(f"\n[2] Alert Rules import ({len(data['groups'])} groups)")
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
                ga["uid"] = rule["uid"]  # 기존 규칙 업데이트
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
        if result is not None:
            print("OK")
        else:
            print("FAILED")

    print("\n[3] 결과 확인")
    result = api(host, auth, "GET",
                 f"/api/ruler/grafana/api/v1/rules/{folder_uid}") or {}
    count = 0
    if isinstance(result, dict):
        for grp_list in result.values():
            if isinstance(grp_list, list):
                for g in grp_list:
                    count += len(g.get("rules", []))
    print(f"  Grafana에 등록된 rules: {count}개")

if __name__ == "__main__":
    main()
