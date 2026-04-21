"""Microsoft Graph SDK client factory for the Planner integration.

Authentication uses :class:`azure.identity.DefaultAzureCredential`, which
resolves credentials from the following chain (in order):

1. Environment variables (``AZURE_CLIENT_ID``, ``AZURE_TENANT_ID``,
   ``AZURE_CLIENT_SECRET`` / ``AZURE_CLIENT_CERTIFICATE_PATH``)
2. Workload Identity (Azure Kubernetes Service)
3. Managed Identity (Azure App Service / Functions / VMs)
4. Azure CLI / Azure Developer CLI (local development)

Required application permissions (Microsoft Graph):
    - ``Tasks.ReadWrite``
    - ``Group.Read.All``  (to resolve the owning Microsoft 365 group)

Environment variables consumed by this module:

``PLANNER_TENANT_ID``
    Azure AD tenant ID. Falls back to ``AZURE_TENANT_ID``.
"""

from __future__ import annotations

import os
from typing import List, Optional

from azure.identity import DefaultAzureCredential
from kiota_authentication_azure.azure_identity_authentication_provider import (
    AzureIdentityAuthenticationProvider,
)
from msgraph import GraphServiceClient
from msgraph.generated.models.o_data_errors.o_data_error import ODataError

__all__ = ["ODataError", "PlannerClient"]


class PlannerClient:
    """Thin wrapper around :class:`msgraph.GraphServiceClient`.

    Instantiate once per function invocation (or reuse across invocations
    when hosted as a singleton in a long-lived Azure Function process).

    Parameters
    ----------
    tenant_id:
        Azure AD tenant ID.  Defaults to the ``PLANNER_TENANT_ID`` or
        ``AZURE_TENANT_ID`` environment variable.
    scopes:
        OAuth 2.0 scopes requested.  Defaults to the Graph default scope.
    credential:
        Pre-built :class:`~azure.identity.DefaultAzureCredential` or any
        compatible ``TokenCredential``.  When *None* a new
        :class:`~azure.identity.DefaultAzureCredential` is constructed.

    Attributes
    ----------
    graph : GraphServiceClient
        The authenticated Microsoft Graph client, ready to use.
    """

    _DEFAULT_SCOPES = ["https://graph.microsoft.com/.default"]

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        credential: Optional[DefaultAzureCredential] = None,
    ) -> None:
        self._tenant_id = (
            tenant_id
            or os.environ.get("PLANNER_TENANT_ID")
            or os.environ.get("AZURE_TENANT_ID")
        )
        self._scopes = scopes or self._DEFAULT_SCOPES
        self._credential = credential or DefaultAzureCredential()
        self.graph: GraphServiceClient = self._build_client()

    # ── Private helpers ──────────────────────────────────────────────────────

    def _build_client(self) -> GraphServiceClient:
        """Construct and return the authenticated Graph client."""
        auth_provider = AzureIdentityAuthenticationProvider(
            credentials=self._credential,
            scopes=self._scopes,
        )
        return GraphServiceClient(
            request_adapter=auth_provider,
            scopes=self._scopes,
        )
