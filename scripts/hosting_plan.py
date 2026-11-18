"""Render review-only hosting files from verified, non-secret provider metadata."""

import argparse
import ast
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from classync_contracts.cloud_run import run_origin
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

ROOT = Path(__file__).resolve().parents[1]
ROLES = ("academic", "scheduling", "gateway")
DATABASE = {"academic": "ACADEMIC", "scheduling": "SCHEDULING", "gateway": "IDENTITY"}
CLIENT_FIELDS = {
    "apiKey": "VITE_FIREBASE_API_KEY", "authDomain": "VITE_FIREBASE_AUTH_DOMAIN",
    "projectId": "VITE_FIREBASE_PROJECT_ID", "appId": "VITE_FIREBASE_APP_ID",
    "storageBucket": "VITE_FIREBASE_STORAGE_BUCKET",
    "messagingSenderId": "VITE_FIREBASE_MESSAGING_SENDER_ID",
}
PROTECTED_PRESENTATION = "class-sync-bhiv"
SQL_CA_PATH = "/var/run/classsync/sql-ca"


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SecretRef(Closed):
    name: str = Field(pattern=r"^[A-Za-z0-9_-]{1,255}$")
    version: int = Field(gt=0)

    def key_ref(self):
        return {"name": self.name, "key": str(self.version)}


class WebRegistration(Closed):
    apiKey: str = Field(pattern=r"^[A-Za-z0-9_-]{25,100}$")
    authDomain: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$")
    projectId: str = Field(pattern=r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
    appId: str = Field(pattern=r"^1:[0-9]+:web:[a-f0-9]+$")
    storageBucket: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9.-]+$")
    messagingSenderId: str | None = Field(default=None, pattern=r"^[0-9]+$")

    @model_validator(mode="after")
    def project_binding(self):
        if (self.projectId.startswith("demo-") or ".." in self.authDomain
                or self.authDomain.endswith(".localhost")):
            raise ValueError("Hosted Firebase registration required")
        if self.messagingSenderId and self.appId.split(":")[1] != self.messagingSenderId:
            raise ValueError("Web app and sender project numbers disagree")
        return self


class Service(Closed):
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{0,47}[a-z0-9]$")
    origin: str
    image: str = Field(pattern=r"^[a-z0-9-]+-docker\.pkg\.dev/[a-z0-9/_-]+@sha256:[a-f0-9]{64}$")
    identity: str = Field(pattern=r"^[a-z0-9-]+@[a-z0-9-]+\.iam\.gserviceaccount\.com$")
    database_secret: SecretRef

    _origin = field_validator("origin")(run_origin)


class HostingMetadata(Closed):
    profile: Literal["preview", "production"]
    cloud_project: str = Field(pattern=r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
    region: str = Field(pattern=r"^[a-z]+(?:-[a-z]+)+[0-9]+$")
    tenant: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")
    network: str = Field(pattern=r"^[a-z][a-z0-9-]{0,62}$")
    subnet: str = Field(pattern=r"^[a-z][a-z0-9-]{0,62}$")
    vercel_project: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,98}[a-z0-9]$")
    vercel_origin: str
    source_branch: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9/_-]{0,127}$")
    production_branch: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9/_-]{0,127}$")
    firebase_web: WebRegistration
    sql_root_ca: SecretRef | None = None
    services: dict[Literal["academic", "scheduling", "gateway"], Service]

    @field_validator("vercel_origin")
    @classmethod
    def frontend_origin(cls, value):
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https" or not parsed.hostname
            or value != "https://" + parsed.hostname
            or not re.fullmatch(r"[a-z0-9][a-z0-9.-]*\.[a-z]{2,}", parsed.hostname)
            or ".." in parsed.hostname or parsed.hostname.endswith(".localhost")
            or parsed.hostname == PROTECTED_PRESENTATION + ".vercel.app"
        ):
            raise ValueError("Use an exact, separate hosted frontend origin")
        return value

    @model_validator(mode="after")
    def validate_isolation(self):
        if self.vercel_project == PROTECTED_PRESENTATION:
            raise ValueError("The public presentation project is protected")
        if self.firebase_web.projectId != self.cloud_project:
            raise ValueError("Firebase and Cloud Run must use the selected project")
        if (self.profile == "production") != (self.source_branch == self.production_branch):
            raise ValueError("Preview and production source branches must be separated")
        if set(self.services) != set(ROLES):
            raise ValueError("All three existing service descriptors are required")
        for attr in ("name", "origin", "image", "identity"):
            if len({getattr(s, attr) for s in self.services.values()}) != len(ROLES):
                raise ValueError("Each service must have its own " + attr)
        if len({s.database_secret.name for s in self.services.values()}) != len(ROLES):
            raise ValueError("Each service requires a distinct database secret")
        for role, svc in self.services.items():
            path = svc.image.split("/")
            if (path[1] != self.cloud_project or path[-1].split("@")[0] != role
                    or not svc.identity.endswith("@" + self.cloud_project
                                                 + ".iam.gserviceaccount.com")):
                raise ValueError("Service image and identity must belong to the selected project")
        return self


def render(metadata):
    web = {
        CLIENT_FIELDS[key]: value for key, value in metadata.firebase_web.model_dump().items()
        if value is not None
    }
    web.update(CLASSSYNC_BUILD_TARGET="connected", VITE_CLASSSYNC_MODE="institutional",
               VITE_API_BASE_URL="/api/v1", VITE_ENABLE_ROLE_PREVIEW="false",
               VITE_ENABLE_PRESENTATION_SAMPLE="false")
    gateway_origin = metadata.services["gateway"].origin
    vercel = {
        "$schema": "https://openapi.vercel.sh/vercel.json",
        "framework": "vite", "installCommand": "npm ci", "buildCommand": "npm run build",
        "outputDirectory": "apps/web/dist",
        "rewrites": [
            {"source": "/api/v1/:path*", "destination": gateway_origin + "/api/v1/:path*"},
            *({"source": route, "destination": "/index.html"} for route in (
                "/", "/auth/:path*", "/forbidden", "/student/:path*",
                "/teacher/:path*", "/admin/:path*",
            )),
        ],
        "headers": [
            {"source": "/(.*)", "headers": [
                {"key": "X-Content-Type-Options", "value": "nosniff"},
                {"key": "Referrer-Policy", "value": "no-referrer"},
                {"key": "Content-Security-Policy",
                 "value": "frame-ancestors 'none'; object-src 'none'; base-uri 'self'"},
            ]},
            {"source": "/api/v1/:path*",
             "headers": [{"key": "Cache-Control", "value": "no-store"}]},
        ],
    }
    result = {
        "vercel.connected.json": vercel,
        "vercel.variables.json": {
            "target": metadata.profile, "project": metadata.vercel_project, "values": web,
        },
    }
    for role, svc in metadata.services.items():
        prefix = DATABASE[role]
        settings = {
            "CLASSSYNC_SERVICE": role, "CLASSSYNC_ENV": "production",
            "FIREBASE_PROJECT_ID": metadata.cloud_project, "FIREBASE_USE_ADC": "true",
            "INSTITUTIONAL_TENANT_ID": metadata.tenant, "CLOUD_RUN_IAM_ENABLED": "true",
            "ENABLE_SCHEDULING_SANDBOX": "false", "ENABLE_TEST_IDENTITY_ADAPTERS": "false",
            "DATABASE_POOL_SIZE": "2", prefix + "_DATABASE_TRANSPORT": "verify-full",
        }
        if role in {"scheduling", "gateway"}:
            settings["ACADEMIC_SERVICE_URL"] = metadata.services["academic"].origin
        if role == "gateway":
            settings.update(
                SCHEDULING_SERVICE_URL=metadata.services["scheduling"].origin,
                CORS_ORIGINS=json.dumps([metadata.vercel_origin]),
                ALLOW_UNAUTHENTICATED_DEVELOPMENT="false", COURSE_CLOUD_ENABLED="false",
                REGISTRATION_MAX_BYTES="5000000", REGISTRATION_MAX_PAGES="5",
                REGISTRATION_TIMEOUT_SECONDS="20", REGISTRATION_RETENTION_SECONDS="900",
            )
        if metadata.sql_root_ca:
            settings["POSTGRES_TLS_ROOT_CERT"] = SQL_CA_PATH + "/server-ca.pem"
        container = {
            "image": svc.image, "ports": [{"containerPort": 8080}],
            "env": [
                *({"name": key, "value": value} for key, value in settings.items()),
                {"name": prefix + "_DATABASE_URL",
                 "valueFrom": {"secretKeyRef": svc.database_secret.key_ref()}},
            ],
            "resources": {"limits": {"cpu": "1", "memory": "1Gi"}},
            "startupProbe": {"httpGet": {"path": "/health", "port": 8080},
                             "periodSeconds": 5, "failureThreshold": 6},
            "livenessProbe": {"httpGet": {"path": "/health", "port": 8080},
                              "periodSeconds": 30, "timeoutSeconds": 2},
        }
        spec = {"serviceAccountName": svc.identity, "containerConcurrency": 4,
                "timeoutSeconds": 60, "containers": [container]}
        if metadata.sql_root_ca:
            container["volumeMounts"] = [{"name": "sql-ca", "mountPath": SQL_CA_PATH}]
            spec["volumes"] = [{"name": "sql-ca", "secret": {
                "secretName": metadata.sql_root_ca.name,
                "items": [{"key": str(metadata.sql_root_ca.version), "path": "server-ca.pem"}],
            }}]
        result[f"cloudrun.{role}.json"] = {
            "apiVersion": "serving.knative.dev/v1", "kind": "Service",
            "metadata": {"name": svc.name,
                         "annotations": {"run.googleapis.com/ingress": "all"}},
            "spec": {"template": {"metadata": {"annotations": {
                "autoscaling.knative.dev/maxScale": "1",
                "run.googleapis.com/execution-environment": "gen2",
                "run.googleapis.com/network-interfaces": json.dumps(
                    [{"network": metadata.network, "subnetwork": metadata.subnet}]
                ),
                "run.googleapis.com/vpc-access-egress": "private-ranges-only",
            }}, "spec": spec}},
        }
    result["review.json"] = {
        "profile": metadata.profile, "cloud_project": metadata.cloud_project,
        "region": metadata.region, "vercel_project": metadata.vercel_project,
        "source_branch": metadata.source_branch, "production_branch": metadata.production_branch,
        "node_version": "22.x", "deploy_authorized": False,
        "gateway": "Public Cloud Run invoker; protected Firebase API routes",
        "academic_scheduling": "IAM-only invocation; never grant allUsers",
        "blockers": ["Firestore authority and publication fencing", "durable OCR review",
                     "native Linux and remote CI", "npm audit and hosted acceptance"],
    }
    return result


def inventory():
    shared = (
        "packages/api-contracts/classync_contracts/firebase.py",
        "packages/api-contracts/classync_contracts/scheduling_security.py",
    )

    def settings(path):
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
        return {field.target.id.upper() for cls in tree.body
                if isinstance(cls, ast.ClassDef) and cls.name.endswith("Settings")
                for field in cls.body if isinstance(field, ast.AnnAssign)
                and isinstance(field.target, ast.Name)}

    common = set().union(*(settings(path) for path in shared))
    paths = [ROOT / "apps/web/vite.config.ts", *list((ROOT / "apps/web/src").rglob("*.ts")),
             *list((ROOT / "apps/web/src").rglob("*.tsx"))]
    frontend = set().union(*(set(re.findall(r"\bVITE_[A-Z0-9_]+", p.read_text(encoding="utf-8")))
                             for p in paths if ".test." not in p.name))
    return {
        "web": sorted(frontend | {"CLASSSYNC_BUILD_TARGET", "CLASSSYNC_GATEWAY_URL"}),
        **{role: sorted(common | settings(f"services/{role}/app/main.py")) for role in ROLES},
        "container_platform": ["CLASSSYNC_SERVICE", "K_SERVICE", "PORT"],
        "build_platform": ["GITHUB_SHA", "NODE_ENV", "VERCEL_GIT_COMMIT_SHA"],
        "emulator_only": ["CLASSSYNC_AUTH_TOOLS_ROOT", "CLASSSYNC_DEV_PORT",
                          "CLASSSYNC_FIRESTORE_EMULATOR_JAR", "CLASSSYNC_POSTGRES_BIN",
                          "FIREBASE_AUTH_EMULATOR_HOST", "FIRESTORE_EMULATOR_HOST"],
        "credential_lookup": ["GOOGLE_APPLICATION_CREDENTIALS"],
    }


def provider_json(tool, arguments):
    executable = shutil.which(tool)
    if executable is None:
        raise ValueError(f"{tool} CLI is not installed")
    directory = ROOT / "var/hosting"
    directory.mkdir(parents=True, exist_ok=True)
    try:
        command = subprocess.run(
            [executable, *arguments], cwd=directory, capture_output=True, check=True,
            timeout=30, encoding="utf-8",
        )
        return json.loads(command.stdout)
    except (subprocess.SubprocessError, OSError, ValueError) as error:
        raise ValueError(f"{tool} read-only metadata lookup failed") from error


def refresh_provider_values(selection, web_app_id=None):
    """Resolve only client-safe SDK settings and the selected services' public metadata."""
    project, region = selection["cloud_project"], selection["region"]
    if (not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", project)
            or not re.fullmatch(r"[a-z]+(?:-[a-z]+)+[0-9]+", region)
            or selection["vercel_project"] == PROTECTED_PRESENTATION
            or set(selection["services"]) != set(ROLES)):
        raise ValueError("Invalid target selection")
    if web_app_id and not re.fullmatch(r"1:[0-9]+:web:[a-f0-9]+", web_app_id):
        raise ValueError("Invalid Firebase Web App selector")
    sdk = provider_json("firebase", [
        "apps:sdkconfig", "WEB", *([web_app_id] if web_app_id else []),
        "--project", project, "--json", "--non-interactive",
    ])["result"]["sdkConfig"]
    selection["firebase_web"] = {key: sdk[key] for key in CLIENT_FIELDS if key in sdk}
    for role in ROLES:
        service = selection["services"][role]
        name = service["name"]
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,47}[a-z0-9]", name):
            raise ValueError("Invalid Cloud Run service selector")
        remote = provider_json("gcloud", [
            "run", "services", "describe", name, "--project", project, "--region", region,
            "--quiet", "--format=json(status.url,spec.template.spec.serviceAccountName)",
        ])
        template = remote["spec"]["template"]["spec"]
        # A deployed image (tag or digest) is not the reviewed feature-worktree artifact.
        # Never substitute a serving revision's image for the explicitly selected digest.
        service.update(origin=remote["status"]["url"], identity=template["serviceAccountName"])
    return selection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--inventory", action="store_true")
    parser.add_argument("--schema", action="store_true")
    parser.add_argument("--refresh-provider-values", action="store_true")
    parser.add_argument("--firebase-app-id")
    args = parser.parse_args()
    if args.inventory or args.schema:
        print(json.dumps(inventory() if args.inventory else HostingMetadata.model_json_schema(),
                         indent=2))
        return
    if not args.metadata or not args.output:
        parser.error("Provide --metadata and a new --output inside var/hosting")
    output = args.output.resolve()
    allowed = (ROOT / "var/hosting").resolve()
    if output == allowed or not output.is_relative_to(allowed):
        parser.error("Output must be a new directory inside the worktree's var/hosting")
    try:
        selection = json.loads(args.metadata.read_bytes())
        if args.refresh_provider_values:
            selection = refresh_provider_values(selection, args.firebase_app_id)
        metadata = HostingMetadata.model_validate(selection)
    except ValidationError as error:
        # The input may have accidentally included a credential: never echo input values.
        parser.error(f"Invalid provider metadata ({error.error_count()} validation errors)")
    except (TypeError, KeyError, ValueError, OSError):
        parser.error("Provider metadata could not be read. Check target selection and CLI login.")
    files = render(metadata)
    output.mkdir(parents=True, exist_ok=False)
    for name, value in files.items():
        with (output / name).open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(value, indent=2) + "\n")
    print("Rendered review-only hosting files. No provider changes were made.")


if __name__ == "__main__":
    main()
