"""Bicep deployment tool using the Azure Python SDK."""

from __future__ import annotations

import datetime
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.resource.resources.models import (
    Deployment,
    DeploymentMode,
    DeploymentProperties,
)

logger = logging.getLogger(__name__)

# Repository root is two levels above this file: subconscious/deploy.py → subconscious/ → repo root
_REPO_ROOT = Path(__file__).parent.parent


def _compile_bicep(bicep_path: Path) -> dict[str, Any]:
    """Compile a Bicep file to an ARM JSON template dict using the Azure CLI."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        subprocess.run(
            [
                "az",
                "bicep",
                "build",
                "--file",
                str(bicep_path),
                "--outfile",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(tmp_path.read_text(encoding="utf-8"))
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Bicep compilation failed for {bicep_path.name}: {exc.stderr}"
        ) from exc
    except FileNotFoundError:
        raise RuntimeError(
            "Azure CLI (az) is not available. "
            "Pre-compile .bicep files to .json to use this tool without the CLI."
        ) from None
    finally:
        tmp_path.unlink(missing_ok=True)


def execute_bicep_deployment(
    bicep_file: str,
    resource_group: str,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deploy an Azure Bicep template via the Azure Python SDK.

    Args:
        bicep_file: Repository-relative path to the .bicep file (e.g. ``infra/main.bicep``).
        resource_group: Target Azure resource group name.
        parameters: Optional dict of ARM template parameter values.

    Returns:
        A dict with deployment metadata (name, resource group, status).
    """
    bicep_path = (_REPO_ROOT / bicep_file).resolve()
    if not bicep_path.exists():
        raise FileNotFoundError(f"Bicep file not found: {bicep_path}")

    # Prefer a pre-compiled ARM JSON template alongside the .bicep file
    arm_path = bicep_path.with_suffix(".json")
    if arm_path.exists():
        template: dict[str, Any] = json.loads(arm_path.read_text(encoding="utf-8"))
        logger.info("Using pre-compiled ARM template: %s", arm_path.name)
    else:
        logger.info("Compiling Bicep file: %s", bicep_path.name)
        template = _compile_bicep(bicep_path)

    deployment_params: dict[str, Any] = {
        param_name: {"value": param_value}
        for param_name, param_value in (parameters or {}).items()
    }
    deployment_name = (
        f"mcp-deploy-{datetime.datetime.now(datetime.UTC).strftime('%Y%m%d%H%M%S')}"
    )

    credential = DefaultAzureCredential()
    subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
    rm_client = ResourceManagementClient(credential, subscription_id)

    rm_client.deployments.begin_create_or_update(
        resource_group_name=resource_group,
        deployment_name=deployment_name,
        parameters=Deployment(
            properties=DeploymentProperties(
                mode=DeploymentMode.INCREMENTAL,
                template=template,
                parameters=deployment_params,
            )
        ),
    )
    logger.info(
        "Deployment '%s' started for resource group '%s'",
        deployment_name,
        resource_group,
    )
    return {
        "deployment_name": deployment_name,
        "resource_group": resource_group,
        "bicep_file": bicep_file,
        "status": "started",
    }
