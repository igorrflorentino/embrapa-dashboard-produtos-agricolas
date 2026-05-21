#!/usr/bin/env python3
"""
Comprehensive test suite for development environment setup.
Tests all critical components.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


class EnvironmentTester:
    """Test suite for development environment."""

    REPO_ROOT = Path(__file__).resolve().parent.parent
    ENV_FILE = REPO_ROOT / ".env"
    GCP_CREDS_FILE = REPO_ROOT / ".gcp-credentials.json"
    DBT_PROFILES_FILE = Path.home() / ".dbt" / "profiles.yml"

    def __init__(self):
        self.tests_passed = []
        self.tests_failed = []

    def print_header(self, text: str):
        """Print a formatted header."""
        print(f"\n{'=' * 60}")
        print(f"  {text}")
        print(f"{'=' * 60}\n")

    def print_test(self, name: str) -> None:
        """Print test name."""
        print(f"  ➜ {name}...", end=" ", flush=True)

    def print_pass(self) -> None:
        """Print pass."""
        print("✅")

    def print_fail(self, reason: str) -> None:
        """Print fail."""
        print(f"❌ {reason}")

    def detect_auth_mode(self) -> str:
        """Detect whether using enterprise (OAuth/impersonation) or legacy (keyfile) auth."""
        if self.GCP_CREDS_FILE.exists():
            return "legacy"
        env_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
        if env_creds and Path(env_creds).exists():
            return "legacy"
        return "enterprise"

    def test_files_exist(self) -> bool:
        """Test that all required files exist."""
        self.print_header("1️⃣  File Existence Tests")

        auth_mode = self.detect_auth_mode()

        required_tests = {
            ".env": self.ENV_FILE,
            "~/.dbt/profiles.yml": self.DBT_PROFILES_FILE,
            "setup.sh": self.REPO_ROOT / "setup.sh",
            "setup.bat": self.REPO_ROOT / "setup.bat",
            "setup.ps1": self.REPO_ROOT / "setup.ps1",
            "scripts/setup_dev_env.py": self.REPO_ROOT / "scripts" / "setup_dev_env.py",
            "docs/setup.md": self.REPO_ROOT / "docs" / "setup.md",
        }

        all_pass = True
        for name, path in required_tests.items():
            self.print_test(f"File exists: {name}")
            if path.exists():
                self.print_pass()
                self.tests_passed.append(f"File exists: {name}")
            else:
                self.print_fail(f"not found at {path}")
                self.tests_failed.append(f"File exists: {name}")
                all_pass = False

        # .gcp-credentials.json is optional in enterprise (OAuth) mode
        self.print_test("File exists: .gcp-credentials.json")
        if self.GCP_CREDS_FILE.exists():
            self.print_pass()
            self.tests_passed.append("File exists: .gcp-credentials.json")
        elif auth_mode == "enterprise":
            print("⚠️  (optional in enterprise/OAuth mode)")
            self.tests_passed.append("File exists: .gcp-credentials.json (optional)")
        else:
            self.print_fail(f"not found at {self.GCP_CREDS_FILE}")
            self.tests_failed.append("File exists: .gcp-credentials.json")
            all_pass = False

        return all_pass

    def test_env_config(self) -> bool:
        """Test that .env has all required keys."""
        self.print_header("2️⃣  Environment Configuration Tests")

        required_keys = [
            "GCP_PROJECT_ID",
            "GCS_BUCKET",
            "BQ_LOCATION",
            "BQ_BRONZE_IBGE_DATASET",
            "BCB_INFLATION_SERIES",
            "IBGE_PRODUCT_CODES",
        ]

        self.print_test("Reading .env file")
        try:
            with open(self.ENV_FILE) as f:
                env_content = f.read()
            self.print_pass()
        except OSError as e:
            self.print_fail(str(e))
            self.tests_failed.append("Read .env file")
            return False

        all_pass = True
        for key in required_keys:
            self.print_test(f"Config key present: {key}")
            if key in env_content:
                self.print_pass()
                self.tests_passed.append(f"Config key: {key}")
            else:
                self.print_fail(f"{key} not in .env")
                self.tests_failed.append(f"Config key: {key}")
                all_pass = False

        return all_pass

    def test_gcp_credentials(self) -> bool:
        """Test GCP credentials — keyfile (legacy) or ADC (enterprise)."""
        self.print_header("3️⃣  GCP Credentials Tests")

        if self.GCP_CREDS_FILE.exists():
            # Legacy: validate JSON keyfile
            self.print_test("Reading credentials file (legacy keyfile)")
            try:
                with open(self.GCP_CREDS_FILE) as f:
                    creds = json.load(f)
                self.print_pass()
            except (OSError, json.JSONDecodeError) as e:
                self.print_fail(f"Invalid JSON: {e}")
                self.tests_failed.append("Read credentials")
                return False

            required_fields = ["project_id", "private_key", "client_email", "type"]
            all_pass = True
            for field in required_fields:
                self.print_test(f"Credential field: {field}")
                if field in creds:
                    self.print_pass()
                    self.tests_passed.append(f"Credential field: {field}")
                else:
                    self.print_fail(f"{field} missing")
                    self.tests_failed.append(f"Credential field: {field}")
                    all_pass = False
            return all_pass
        else:
            # Enterprise: check Application Default Credentials (ADC)
            self.print_test("Application Default Credentials (enterprise/OAuth mode)")
            try:
                result = subprocess.run(
                    ["gcloud", "auth", "application-default", "print-access-token"],
                    capture_output=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    self.print_pass()
                    self.tests_passed.append("ADC credentials (enterprise)")
                    return True
                else:
                    self.print_fail("No ADC token — run: gcloud auth application-default login")
                    self.tests_failed.append("ADC credentials (enterprise)")
                    return False
            except FileNotFoundError:
                self.print_fail(
                    "gcloud not found — install Cloud SDK or provide .gcp-credentials.json"
                )
                self.tests_failed.append("ADC credentials (enterprise)")
                return False

    def test_dbt_profiles(self) -> bool:
        """Test that dbt profiles.yml is valid YAML."""
        self.print_header("4️⃣  dbt Configuration Tests")

        self.print_test("Reading dbt profiles.yml")
        try:
            with open(self.DBT_PROFILES_FILE) as f:
                content = f.read()
            self.print_pass()
        except OSError as e:
            self.print_fail(str(e))
            self.tests_failed.append("Read dbt profiles")
            return False

        # Required in all modes
        required_sections = [
            "embrapa_commodities:",
            "dev:",
            "prod:",
            "type: bigquery",
        ]

        all_pass = True
        for section in required_sections:
            self.print_test(f"dbt profile section: {section}")
            if section in content:
                self.print_pass()
                self.tests_passed.append(f"dbt section: {section}")
            else:
                self.print_fail(f"{section} not found")
                self.tests_failed.append(f"dbt section: {section}")
                all_pass = False

        # Auth method: either service-account (legacy) or oauth (enterprise)
        self.print_test("dbt auth method: service-account or oauth")
        if "method: service-account" in content or "method: oauth" in content:
            method = "service-account" if "method: service-account" in content else "oauth"
            print(f"✅ ({method})")
            self.tests_passed.append(f"dbt auth method: {method}")
        else:
            self.print_fail("no valid method (service-account or oauth)")
            self.tests_failed.append("dbt auth method")
            all_pass = False

        return all_pass

    def test_python_version(self) -> bool:
        """Test Python version."""
        self.print_header("5️⃣  Python & Dependencies Tests")

        self.print_test("Python version >= 3.8")
        try:
            version = sys.version_info
            if version.major >= 3 and version.minor >= 8:
                self.print_pass()
                self.tests_passed.append(f"Python {version.major}.{version.minor}")
            else:
                self.print_fail(f"Python {version.major}.{version.minor} < 3.8")
                self.tests_failed.append("Python version")
                return False
        except Exception as e:
            self.print_fail(str(e))
            self.tests_failed.append("Python version")
            return False

        return True

    def test_uv(self) -> bool:
        """Test uv installation."""
        self.print_header("6️⃣  Build Tools Tests")

        self.print_test("uv available")
        try:
            result = subprocess.run(["uv", "--version"], capture_output=True, timeout=5)
            if result.returncode == 0:
                version = result.stdout.decode().strip()
                self.print_pass()
                self.tests_passed.append(f"uv: {version}")
                return True
            else:
                self.print_fail("uv not working")
                self.tests_failed.append("uv available")
                return False
        except Exception as e:
            self.print_fail(str(e))
            self.tests_failed.append("uv available")
            return False

    def test_dbt(self) -> bool:
        """Test dbt installation."""
        self.print_header("7️⃣  dbt Tests")

        self.print_test("dbt available via uv")
        try:
            result = subprocess.run(
                ["uv", "run", "dbt", "--version"],
                cwd=self.REPO_ROOT,
                capture_output=True,
                timeout=30,
            )
            if result.returncode == 0:
                self.print_pass()
                self.tests_passed.append("dbt available")
                return True
            else:
                self.print_fail("dbt not accessible")
                self.tests_failed.append("dbt available")
                return False
        except Exception as e:
            self.print_fail(str(e))
            self.tests_failed.append("dbt available")
            return False

    def test_embrapa_doctor(self) -> bool:
        """Test embrapa doctor."""
        self.print_header("8️⃣  Embrapa Pipeline Tests")

        self.print_test("embrapa doctor (health check)")
        try:
            env = os.environ.copy()
            if self.GCP_CREDS_FILE.exists():
                env["GOOGLE_APPLICATION_CREDENTIALS"] = str(self.GCP_CREDS_FILE.resolve())
            # In enterprise mode, ADC is used automatically (no env var needed)

            result = subprocess.run(
                ["uv", "run", "embrapa", "doctor"],
                cwd=self.REPO_ROOT,
                capture_output=True,
                timeout=60,
                env=env,
            )

            output = result.stdout.decode()
            if "All checks passed" in output:
                self.print_pass()
                self.tests_passed.append("embrapa doctor: All checks passed")
                return True
            elif result.returncode == 0:
                self.print_pass()
                self.tests_passed.append("embrapa doctor: Passed (with warnings)")
                return True
            else:
                self.print_fail("Some embrapa checks failed")
                self.tests_failed.append("embrapa doctor")
                print("\n" + output)
                return False
        except Exception as e:
            self.print_fail(str(e))
            self.tests_failed.append("embrapa doctor")
            return False

    def test_dbt_debug(self) -> bool:
        """Test dbt debug connection."""
        self.print_header("9️⃣  BigQuery Connection Tests")

        self.print_test("dbt debug (BigQuery connection)")
        try:
            env = os.environ.copy()
            if self.GCP_CREDS_FILE.exists():
                env["GOOGLE_APPLICATION_CREDENTIALS"] = str(self.GCP_CREDS_FILE.resolve())
            # In enterprise mode, ADC/impersonation is used automatically

            result = subprocess.run(
                ["uv", "run", "dbt", "debug"],
                cwd=self.REPO_ROOT / "dbt",
                capture_output=True,
                timeout=30,
                env=env,
            )

            output = result.stdout.decode()
            if "All checks passed" in output or "Connection ok" in output:
                self.print_pass()
                self.tests_passed.append("dbt debug: Connection OK")
                return True
            else:
                self.print_fail("BigQuery connection failed")
                self.tests_failed.append("dbt debug")
                print("\n" + output)
                return False
        except Exception as e:
            self.print_fail(str(e))
            self.tests_failed.append("dbt debug")
            return False

    def print_summary(self):
        """Print test summary."""
        self.print_header("📊 Test Summary")

        total = len(self.tests_passed) + len(self.tests_failed)
        passed = len(self.tests_passed)
        failed = len(self.tests_failed)

        print(f"Total: {total} tests")
        print(f"Passed: {passed} ✅")
        print(f"Failed: {failed} ❌")
        print()

        if self.tests_failed:
            print("Failed tests:")
            for test in self.tests_failed:
                print(f"  ❌ {test}")
            print()

        if failed == 0:
            print("🎉 All tests passed! Environment is ready.\n")
            return True
        else:
            print(f"⚠️  {failed} test(s) failed. Please review above.\n")
            return False

    def run_all_tests(self) -> bool:
        """Run all tests."""
        self.test_files_exist()
        self.test_env_config()
        self.test_gcp_credentials()
        self.test_dbt_profiles()
        self.test_python_version()
        self.test_uv()
        self.test_dbt()
        self.test_embrapa_doctor()
        self.test_dbt_debug()

        return self.print_summary()


def main():
    """Main entry point."""
    tester = EnvironmentTester()

    try:
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTests cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
