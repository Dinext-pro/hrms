"""Install HRMS on the Frappe and ERPNext 15.123.0 pair and, when asked, run one Cypress spec.

Frappe and ERPNext come from their paired upgrade branches. This does not touch a
running site. Compatibility acceptance stops after migrate, build and ping.
Cypress acceptance then completes setup and runs the upstream Frappe awesome-bar spec.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

role = sys.argv[1]
if role not in {"compatibility", "cypress"}:
    raise SystemExit("role must be compatibility or cypress")

workspace = Path(os.environ["GITHUB_WORKSPACE"]).resolve()
bench = Path(os.environ["RUNNER_TEMP"]) / "dinext-hrms-bench"
site = "ci.test"
admin_password = "ci-admin"


def run(*args, cwd=None, timeout=2400, env=None):
    print("+", " ".join(str(item) for item in args), flush=True)
    subprocess.run([str(item) for item in args], cwd=cwd, check=True, timeout=timeout, env=env)


def fetch_repo(repo, ref, name):
    destination = Path(os.environ["RUNNER_TEMP"]) / "dinext-hrms-inputs" / name
    destination.mkdir(parents=True)
    run("git", "init", str(destination))
    run(
        "git", "fetch", "--no-tags", "--depth=1",
        "https://github.com/" + repo + ".git", ref,
        cwd=destination,
    )
    run("git", "checkout", "--detach", "FETCH_HEAD", cwd=destination)
    run("git", "update-ref", "refs/heads/dinext-ci-pinned", "HEAD", cwd=destination)
    return destination


frappe_source = fetch_repo("Dinext-pro/dinext_platform", "dinext/upgrade/v15.123.0", "frappe")
erpnext_source = fetch_repo("Dinext-pro/dinext_erp", "dinext/upgrade/v15.123.0", "erpnext")
run("git", "update-ref", "refs/heads/dinext-ci-input", "HEAD", cwd=frappe_source)
if bench.exists():
    raise SystemExit("Each acceptance run requires a fresh bench")
run(
    "bench", "init", str(bench),
    "--frappe-path", str(frappe_source),
    "--frappe-branch", "dinext-ci-input",
    "--skip-assets", "--skip-redis-config-generation",
    "--python", sys.executable,
    cwd=bench.parent,
)
common = bench / "sites/common_site_config.json"
settings = json.loads(common.read_text())
settings.update({
    "db_host": "127.0.0.1",
    "db_port": 3306,
    "redis_cache": "redis://127.0.0.1:6379/0",
    "redis_queue": "redis://127.0.0.1:6379/1",
    "redis_socketio": "redis://127.0.0.1:6379/2",
    "server_script_enabled": 1,
    "pause_scheduler": 1,
    "mute_emails": True,
})
common.write_text(json.dumps(settings))
run(
    "mariadb", "--host", "127.0.0.1", "--port", "3306", "-u", "root", "-pci",
    "-e", "SET GLOBAL character_set_server='utf8mb4'; SET GLOBAL collation_server='utf8mb4_unicode_ci';",
)
run("bench", "get-app", "--skip-assets", "erpnext", str(erpnext_source), cwd=bench)
run("bench", "get-app", "--skip-assets", "hrms", str(workspace), cwd=bench)
run("bench", "setup", "requirements", cwd=bench)
run(
    "bench", "new-site", site,
    "--db-host", "127.0.0.1", "--no-mariadb-socket",
    "--mariadb-root-password", "ci", "--admin-password", admin_password,
    "--set-default",
    cwd=bench,
)
run("bench", "--site", site, "install-app", "erpnext", cwd=bench)
run("bench", "--site", site, "install-app", "hrms", cwd=bench)
run("bench", "--site", site, "migrate", cwd=bench)
run("bench", "build", cwd=bench)
run("bench", "--site", site, "execute", "frappe.ping", cwd=bench)
version = subprocess.run(
    ["bench", "version"], cwd=bench, check=True, text=True, capture_output=True, timeout=120,
)
print(version.stdout, flush=True)
if version.stdout.count("15.123.0") < 2 or "15.64.5" not in version.stdout:
    raise SystemExit("Expected Frappe 15.123.0, ERPNext 15.123.0 and HRMS 15.64.5")

if role == "compatibility":
    print("HRMS installed on the 15.123.0 pair; migrate and build passed.", flush=True)
    sys.exit(0)

setup_args = {
    "language": "English",
    "email": "test@erpnext.com",
    "full_name": "Test User",
    "password": admin_password,
    "country": "United States",
    "timezone": "America/New_York",
    "currency": "USD",
    "company_name": "Dinext Pair Test",
    "company_abbr": "DPT",
    "chart_of_accounts": "Standard",
    "fy_start_date": "2026-01-01",
    "fy_end_date": "2026-12-31",
    "setup_demo": 0,
}
run(
    "bench", "--site", site, "execute",
    "frappe.desk.page.setup_wizard.setup_wizard.setup_complete",
    "--kwargs", json.dumps(setup_args),
    cwd=bench,
)
run("bench", "--site", site, "execute", "frappe.tests.ui_test_helpers.create_test_user", cwd=bench)
run("bench", "--site", site, "set-config", "host_name", "http://127.0.0.1:8000", cwd=bench)
run("bench", "--site", site, "set-config", "developer_mode", "1", cwd=bench)

log_path = bench / "serve.log"
log_file = log_path.open("w")
server = subprocess.Popen(
    ["bench", "serve", "--port", "8000", "--noreload"],
    cwd=bench, stdout=log_file, stderr=subprocess.STDOUT,
)
try:
    for _ in range(90):
        if server.poll() is not None:
            print(log_path.read_text()[-4000:], flush=True)
            raise SystemExit("bench serve exited before answering")
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/api/method/ping", timeout=3) as response:
                if response.status == 200:
                    break
        except Exception:
            time.sleep(2)
    else:
        print(log_path.read_text()[-4000:], flush=True)
        raise SystemExit("bench serve did not answer")

    frappe_app = bench / "apps/frappe"
    packages = [
        "cypress@^13",
        "@4tw/cypress-drag-drop@^2",
        "cypress-real-events",
        "@testing-library/cypress@^10",
        "@testing-library/dom@8.17.1",
        "@cypress/code-coverage@^3",
    ]
    run("yarn", "add", *packages, "--no-lockfile", cwd=frappe_app, timeout=1800)
    spec = frappe_app / "cypress/integration/awesome_bar.js"
    if not spec.is_file():
        raise SystemExit("Upstream awesome-bar spec is missing")
    env = os.environ.copy()
    env["CYPRESS_baseUrl"] = "http://127.0.0.1:8000"
    env["CYPRESS_adminPassword"] = admin_password
    run(
        "xvfb-run", "-a", "yarn", "exec", "cypress", "run",
        "--browser", "electron", "--spec", str(spec),
        cwd=frappe_app, timeout=1800, env=env,
    )
    print("Cypress awesome-bar spec passed on the HRMS site.", flush=True)
finally:
    server.terminate()
    try:
        server.wait(timeout=20)
    except subprocess.TimeoutExpired:
        server.kill()
    log_file.close()
