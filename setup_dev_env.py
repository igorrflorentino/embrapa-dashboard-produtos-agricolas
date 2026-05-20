#!/usr/bin/env python3
"""
Cross-platform development environment setup script.
Supports Windows, macOS, and Linux with automatic detection.
"""

import os
import sys
import json
import platform
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict, Any


class SetupHelper:
    """Helper for cross-platform environment setup."""

    REPO_ROOT = Path(__file__).parent
    ENV_FILE = REPO_ROOT / ".env"
    DBT_PROFILES_DIR = Path.home() / ".dbt"
    DBT_PROFILES_FILE = DBT_PROFILES_DIR / "profiles.yml"
    GCP_CREDS_FILE = REPO_ROOT / ".gcp-credentials.json"

    ENV_TEMPLATE = """{gcp_config}{bcb_config}{ibge_config}"""

    GCP_CONFIG = """# GCP Configuration
GCP_PROJECT_ID={project_id}
GCS_BUCKET={bucket}
GCS_LANDING_PREFIX=landing
BQ_LOCATION=us-central1

# BigQuery datasets / tables
BQ_BRONZE_IBGE_DATASET=bronze_ibge
BQ_BRONZE_BCB_DATASET=bronze_bcb
BQ_BRONZE_IBGE_TABLE=sidra_t289_raw
BQ_BRONZE_BCB_INFLATION_TABLE=inflation_series_raw
BQ_BRONZE_BCB_CURRENCY_TABLE=currency_series_raw
BQ_SILVER_DATASET=silver
BQ_GOLD_DATASET=gold

"""

    IBGE_CONFIG = """# IBGE PEVS Configuration
IBGE_TABLE_ID=289
IBGE_CLASSIFICATION_ID=193
IBGE_PRODUCT_CODES=3405,3435,3450
IBGE_START_YEAR=1986
IBGE_END_YEAR=2024

"""

    BCB_CONFIG = """# BCB SGS Configuration
BCB_INFLATION_SERIES=433:IPCA,189:IGPM,190:IGPDI
BCB_INFLATION_SERIES_IPCA_CODE=433
BCB_INFLATION_SERIES_IGPM_CODE=189
BCB_CURRENCY_SERIES=3694:USD,4393:EUR,20542:CNY
BCB_START_YEAR=1980
BCB_END_YEAR=2026

"""

    DBT_PROFILES_TEMPLATE = """embrapa_commodities:
  target: dev
  outputs:
    dev:
      type: bigquery
      method: service-account
      project: {project_id}
      dataset: dbt_dev
      location: us-central1
      threads: 4
      job_execution_timeout_seconds: 600
      job_retries: 1
      priority: interactive
      keyfile: {keyfile}

    prod:
      type: bigquery
      method: service-account
      project: {project_id}
      dataset: prod
      location: us-central1
      threads: 8
      job_execution_timeout_seconds: 600
      job_retries: 1
      priority: batch
      keyfile: {keyfile}
"""

    def __init__(self):
        self.os_name = platform.system()
        self.is_windows = self.os_name == "Windows"
        self.is_mac = self.os_name == "Darwin"
        self.is_linux = self.os_name == "Linux"

    def print_header(self, text: str):
        """Print a formatted header."""
        print(f"\n{'='*60}")
        print(f"  {text}")
        print(f"{'='*60}\n")

    def print_step(self, step: int, text: str):
        """Print a step message."""
        print(f"[{step}] {text}")

    def print_success(self, text: str):
        """Print a success message."""
        print(f"  ✅ {text}")

    def print_error(self, text: str):
        """Print an error message."""
        print(f"  ❌ {text}")

    def print_warning(self, text: str):
        """Print a warning message."""
        print(f"  ⚠️  {text}")

    def print_info(self, text: str):
        """Print an info message."""
        print(f"  ℹ️  {text}")

    def get_gcp_credentials(self) -> Optional[Dict[str, Any]]:
        """
        Get GCP credentials with fallback strategy:
        1. Try environment variable GOOGLE_APPLICATION_CREDENTIALS
        2. Try --credentials-file argument
        3. Prompt user to paste JSON
        """
        # Strategy 1: Check environment variable
        env_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if env_creds and Path(env_creds).exists():
            self.print_info(f"Found credentials in GOOGLE_APPLICATION_CREDENTIALS")
            try:
                with open(env_creds) as f:
                    creds = json.load(f)
                    self.print_success(f"Loaded credentials from {env_creds}")
                    return creds
            except (json.JSONDecodeError, IOError) as e:
                self.print_warning(f"Failed to read credentials file: {e}")

        # Strategy 2: Check for --credentials-file argument
        if "--credentials-file" in sys.argv:
            idx = sys.argv.index("--credentials-file")
            if idx + 1 < len(sys.argv):
                creds_path = Path(sys.argv[idx + 1])
                if creds_path.exists():
                    try:
                        with open(creds_path) as f:
                            creds = json.load(f)
                            self.print_success(f"Loaded credentials from {creds_path}")
                            return creds
                    except (json.JSONDecodeError, IOError) as e:
                        self.print_error(f"Failed to read {creds_path}: {e}")

        # Strategy 3: Prompt user
        self.print_info("No credentials found. Paste your GCP service account JSON below.")
        self.print_info("(Press Enter twice when done)")

        lines = []
        empty_count = 0
        try:
            while empty_count < 2:
                line = input()
                if not line.strip():
                    empty_count += 1
                else:
                    empty_count = 0
                    lines.append(line)
        except EOFError:
            self.print_error("No input received. Skipping GCP setup.")
            return None

        if not lines:
            return None

        try:
            json_str = "\n".join(lines)
            creds = json.loads(json_str)
            self.print_success("Credentials parsed successfully")
            return creds
        except json.JSONDecodeError as e:
            self.print_error(f"Invalid JSON: {e}")
            return None

    def save_gcp_credentials(self, creds: Dict[str, Any]) -> bool:
        """Save GCP credentials to file."""
        try:
            with open(self.GCP_CREDS_FILE, "w") as f:
                json.dump(creds, f, indent=2)
            os.chmod(self.GCP_CREDS_FILE, 0o600)
            self.print_success(f"Saved credentials to {self.GCP_CREDS_FILE}")
            return True
        except IOError as e:
            self.print_error(f"Failed to save credentials: {e}")
            return False

    def create_env_file(self, project_id: str, bucket: str) -> bool:
        """Create .env file."""
        try:
            content = self.ENV_TEMPLATE.format(
                gcp_config=self.GCP_CONFIG.format(project_id=project_id, bucket=bucket),
                ibge_config=self.IBGE_CONFIG,
                bcb_config=self.BCB_CONFIG
            )

            self.ENV_FILE.write_text(content)
            self.print_success(f"Created {self.ENV_FILE}")
            return True
        except IOError as e:
            self.print_error(f"Failed to create .env: {e}")
            return False

    def create_dbt_profiles(self, project_id: str) -> bool:
        """Create dbt profiles.yml."""
        try:
            self.DBT_PROFILES_DIR.mkdir(parents=True, exist_ok=True)

            # Use absolute path to credentials
            keyfile = self.GCP_CREDS_FILE.resolve()

            content = self.DBT_PROFILES_TEMPLATE.format(
                project_id=project_id,
                keyfile=str(keyfile)
            )

            self.DBT_PROFILES_FILE.write_text(content)

            # Set restrictive permissions on Linux/Mac
            if not self.is_windows:
                os.chmod(self.DBT_PROFILES_FILE, 0o600)

            self.print_success(f"Created {self.DBT_PROFILES_FILE}")
            return True
        except IOError as e:
            self.print_error(f"Failed to create dbt profiles: {e}")
            return False

    def add_to_gitignore(self) -> bool:
        """Add sensitive files to .gitignore."""
        gitignore = self.REPO_ROOT / ".gitignore"
        entries = [".gcp-credentials.json"]

        try:
            if gitignore.exists():
                content = gitignore.read_text()
            else:
                content = ""

            for entry in entries:
                if entry not in content:
                    content += f"\n{entry}"

            gitignore.write_text(content)
            self.print_success("Updated .gitignore")
            return True
        except IOError as e:
            self.print_error(f"Failed to update .gitignore: {e}")
            return False

    def validate_uv(self) -> bool:
        """Check if uv is available."""
        try:
            result = subprocess.run(
                ["uv", "--version"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.decode().strip()
                self.print_success(f"Found uv: {version}")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        self.print_warning("uv not found. Install from https://github.com/astral-sh/uv")
        return False

    def validate_gcloud(self) -> bool:
        """Check if gcloud CLI is available (optional)."""
        try:
            result = subprocess.run(
                ["gcloud", "--version"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                self.print_success("gcloud CLI found")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        self.print_warning("gcloud CLI not found (optional for this setup)")
        return False

    def run_embrapa_doctor(self) -> bool:
        """Run embrapa doctor to validate setup."""
        try:
            env = os.environ.copy()
            env["GOOGLE_APPLICATION_CREDENTIALS"] = str(self.GCP_CREDS_FILE.resolve())

            result = subprocess.run(
                ["uv", "run", "embrapa", "doctor"],
                cwd=self.REPO_ROOT,
                capture_output=True,
                timeout=60,
                env=env
            )

            output = result.stdout.decode()
            if "All checks passed" in output:
                self.print_success("embrapa doctor: All checks passed!")
                return True
            else:
                self.print_warning("embrapa doctor: Some checks failed")
                print(output)
                return False
        except Exception as e:
            self.print_warning(f"Could not run embrapa doctor: {e}")
            return False

    def run_setup(self) -> bool:
        """Run the complete setup process."""
        self.print_header(f"Development Environment Setup ({self.os_name})")

        # Step 1: Check uv
        self.print_step(1, "Checking uv installation...")
        if not self.validate_uv():
            self.print_error("uv is required. Please install it first.")
            return False

        # Step 2: Check gcloud (optional)
        self.print_step(2, "Checking gcloud CLI (optional)...")
        self.validate_gcloud()

        # Step 3: Get GCP credentials
        self.print_step(3, "Setting up GCP credentials...")
        creds = self.get_gcp_credentials()
        if not creds:
            self.print_error("Cannot proceed without GCP credentials")
            return False

        project_id = creds.get("project_id")
        if not project_id:
            self.print_error("Invalid credentials: missing project_id")
            return False

        bucket = f"{project_id}-datalake"

        # Step 4: Save credentials
        self.print_step(4, "Saving GCP credentials...")
        if not self.save_gcp_credentials(creds):
            return False

        # Step 5: Create .env
        self.print_step(5, "Creating .env file...")
        if not self.create_env_file(project_id, bucket):
            return False

        # Step 6: Create dbt profiles
        self.print_step(6, "Creating dbt profiles...")
        if not self.create_dbt_profiles(project_id):
            return False

        # Step 7: Update .gitignore
        self.print_step(7, "Updating .gitignore...")
        self.add_to_gitignore()

        # Step 8: Validate setup
        self.print_step(8, "Validating setup...")
        doctor_passed = self.run_embrapa_doctor()

        return True


def main():
    """Main entry point."""
    helper = SetupHelper()

    try:
        success = helper.run_setup()

        if success:
            helper.print_header("✅ Setup Complete!")
            print("Your development environment is ready.\n")
            print("Next steps:")
            print("  1. Review .env file and make any necessary changes")
            print("  2. Run: uv run embrapa --help")
            print("  3. Run: make dbt-build (for dbt development)")
            print("  4. Happy coding! 🚀\n")
            sys.exit(0)
        else:
            helper.print_header("❌ Setup Failed")
            print("Please review the errors above and try again.\n")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
