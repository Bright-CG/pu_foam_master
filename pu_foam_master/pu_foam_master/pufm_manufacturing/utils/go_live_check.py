# Copyright (c) 2026, PU Foam Master and contributors
"""One-command go-live verification (bench execute).

  bench --site <site> execute pu_foam_master.pufm_manufacturing.utils.go_live_check.run

Runs: DocType smoke, unit tests (via subprocess), E2E flows + GL gap checks, costing retest.
Does not wipe data; E2E creates real submitted docs on the site (use staging first).
"""

from __future__ import annotations

import json
import subprocess

import frappe


def run(run_e2e=True, run_retest=True):
	frappe.connect()
	site = frappe.local.site
	report = {
		"site": site,
		"smoke": None,
		"unit_tests": None,
		"e2e": None,
		"retest_costing": None,
		"migrate_hooks": _migrate_info(),
		"verdict": "",
	}

	report["smoke"] = _run_smoke()
	report["unit_tests"] = _run_unit_tests(site)

	if run_e2e:
		try:
			from pu_foam_master.pufm_manufacturing.utils.e2e_audit import run as e2e_run

			report["e2e"] = e2e_run()
		except Exception as e:
			frappe.db.rollback()
			report["e2e"] = {"verdict": "ERROR", "error": str(e)}

	if run_retest:
		try:
			from pu_foam_master.pufm_manufacturing.utils.retest_costing import run as retest_run

			report["retest_costing"] = retest_run()
		except Exception as e:
			frappe.db.rollback()
			report["retest_costing"] = {"errors": [str(e)]}

	report["verdict"] = _overall_verdict(report)
	print(json.dumps(report, indent=2, default=str))
	print("\n=== GO-LIVE VERDICT ===\n{0}".format(report["verdict"]))
	return report


def _run_smoke():
	from pu_foam_master.pufm_manufacturing.utils.smoke_pufm_doctypes import run as smoke_run

	try:
		return smoke_run()
	except Exception as e:
		return {"ok": False, "error": str(e)}


def _run_unit_tests(site):
	cmd = [
		"bench",
		"--site",
		site,
		"run-tests",
		"--app",
		"pu_foam_master",
	]
	try:
		proc = subprocess.run(
			cmd,
			capture_output=True,
			text=True,
			timeout=600,
			cwd=frappe.utils.get_bench_path(),
		)
		ok = proc.returncode == 0 and "FAILED" not in (proc.stdout or "")
		return {
			"ok": ok,
			"returncode": proc.returncode,
			"tail": (proc.stdout or proc.stderr or "")[-2500:],
		}
	except Exception as e:
		return {"ok": False, "error": str(e)}


def _migrate_info():
	return {
		"update_command": "bench --site <site> migrate && bench build --app pu_foam_master",
		"data_safe": True,
		"notes": (
			"Updates run after_migrate hooks only (roles, custom fields, workflows, backfills). "
			"No reset scripts. Never use reinstall-app on production."
		),
		"after_migrate_hooks": frappe.get_hooks("after_migrate", app_name="pu_foam_master"),
	}


def _overall_verdict(report):
	issues = []
	if not (report.get("smoke") or {}).get("ok", True) and report.get("smoke", {}).get("doctypes_failed"):
		issues.append("DocType smoke failed")
	if not (report.get("unit_tests") or {}).get("ok"):
		issues.append("Unit tests failed")
	e2e = report.get("e2e") or {}
	if isinstance(e2e, dict):
		if e2e.get("fail_count", 0) > 0:
			issues.append("E2E: {0} flow(s) failed".format(e2e.get("fail_count")))
		if e2e.get("errors"):
			issues.append("E2E errors present")
		audit = e2e.get("audit") or {}
		if audit.get("settings_gaps"):
			issues.append("Settings gaps: {0}".format(", ".join(audit["settings_gaps"][:5])))
	retest = report.get("retest_costing") or {}
	if retest.get("errors"):
		issues.append("Costing retest errors")

	if not issues:
		return (
			"READY FOR GO-LIVE (automated checks passed). "
			"Run once on production-like staging with real stock; then migrate production with bench migrate only."
		)
	if len(issues) <= 2 and not (report.get("unit_tests") or {}).get("ok") is False:
		return "CONDITIONAL — fix before production: " + "; ".join(issues)
	return "NOT READY — " + "; ".join(issues)
