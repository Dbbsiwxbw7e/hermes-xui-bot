"""
Railway GraphQL API client — thin, typed, exception-based.
Every method raises RailwayError on failure; callers decide how to surface it.
"""
import requests

RAILWAY_API_URL = "https://api.railway.app/graphql/v2"


class RailwayError(Exception):
    pass


class RailwayAPI:
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # ── low-level ──────────────────────────────────────────────
    def _gql(self, query: str, variables: dict | None = None) -> dict:
        try:
            resp = requests.post(
                RAILWAY_API_URL,
                json={"query": query, "variables": variables or {}},
                headers=self.headers,
                timeout=30,
            )
        except requests.RequestException as e:
            raise RailwayError(f"خطای شبکه: {e}") from e

        if resp.status_code == 401:
            raise RailwayError("توکن Railway نامعتبره.")
        if resp.status_code != 200:
            raise RailwayError(f"HTTP {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        if data.get("errors"):
            msgs = "; ".join(e.get("message", "?") for e in data["errors"])
            raise RailwayError(f"Railway API: {msgs}")
        return data.get("data", {})

    # ── account ────────────────────────────────────────────────
    def whoami(self) -> tuple[str, str]:
        """Returns (workspace_id, email)."""
        d = self._gql("{ me { email workspaces { id } } }")
        me = d.get("me") or {}
        ws = (me.get("workspaces") or [{}])[0].get("id", "")
        return ws, me.get("email", "")

    # ── projects & services ────────────────────────────────────
    def create_project(self, name: str, workspace_id: str) -> dict:
        d = self._gql(
            """mutation($input: ProjectCreateInput!) {
                 projectCreate(input: $input) { id name environmentId }
               }""",
            {"input": {"name": name, "workspaceId": workspace_id}},
        )
        proj = d.get("projectCreate")
        if not proj:
            raise RailwayError("ساخت پروژه شکست خورد")
        return proj

    def list_projects(self) -> list[dict]:
        d = self._gql(
            "{ me { workspaces { projects(first: 50) { edges { node { id name createdAt } } } } } }"
        )
        out = []
        for ws in (d.get("me") or {}).get("workspaces", []):
            for edge in ws.get("projects", {}).get("edges", []):
                out.append(edge["node"])
        return out

    def delete_project(self, project_id: str) -> bool:
        d = self._gql(
            "mutation($id: String!) { projectDelete(id: $id) }",
            {"id": project_id},
        )
        return bool(d.get("projectDelete"))

    def create_service(self, name: str, project_id: str, image: str) -> dict:
        d = self._gql(
            """mutation($input: ServiceCreateInput!) {
                 serviceCreate(input: $input) { id name }
               }""",
            {"input": {"projectId": project_id, "name": name, "source": {"image": image}}},
        )
        svc = d.get("serviceCreate")
        if not svc:
            raise RailwayError(f"ساخت سرویس {name} شکست خورد")
        return svc

    def deploy(self, service_id: str, environment_id: str) -> None:
        self._gql(
            """mutation($serviceId: String!, $environmentId: String!) {
                 serviceInstanceDeploy(serviceId: $serviceId, environmentId: $environmentId)
               }""",
            {"serviceId": service_id, "environmentId": environment_id},
        )

    def create_domain(self, service_id: str, environment_id: str, target_port: int) -> str:
        d = self._gql(
            """mutation($input: ServiceDomainCreateInput!) {
                 serviceDomainCreate(input: $input) { domain }
               }""",
            {
                "input": {
                    "serviceId": service_id,
                    "environmentId": environment_id,
                    "targetPort": target_port,
                }
            },
        )
        return (d.get("serviceDomainCreate") or {}).get("domain", "")

    def get_environments(self, project_id: str) -> list[dict]:
        d = self._gql(
            """query($projectId: String!) {
                 environments(projectId: $projectId) { edges { node { id name } } }
               }""",
            {"projectId": project_id},
        )
        return [e["node"] for e in d.get("environments", {}).get("edges", [])]

    # ── deployment polling ─────────────────────────────────────
    def latest_deployment(self, service_id: str) -> dict | None:
        d = self._gql(
            """query($id: String!) {
                 service(id: $id) {
                   deployments(last: 1) { edges { node { id status staticUrl } } }
                 }
               }""",
            {"id": service_id},
        )
        edges = ((d.get("service") or {}).get("deployments") or {}).get("edges", [])
        return edges[-1]["node"] if edges else None
