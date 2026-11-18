"""Document each HTTP operation separately and expose verified-token entry in Swagger."""

from copy import copy
from hashlib import sha256

from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute


def install_openapi(app):
    def schema():
        if app.openapi_schema is None:
            routes = []
            for route in app.routes:
                if not isinstance(route, APIRoute):
                    routes.append(route)
                    continue
                for method in sorted(route.methods):
                    documented = copy(route)
                    documented.methods = {method}
                    suffix = sha256(route.path_format.encode()).hexdigest()[:12]
                    documented.operation_id = f"{route.name}_{method.lower()}_{suffix}"
                    routes.append(documented)
            value = get_openapi(title=app.title, version=app.version, routes=routes)
            value.setdefault("components", {}).setdefault("securitySchemes", {})[
                "FirebaseBearer"
            ] = {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Firebase ID token plus current institutional membership.",
            }
            for path, operations in value["paths"].items():
                if not path.startswith("/api/v1/") or "/sandbox/" in path:
                    continue
                for operation in operations.values():
                    if not isinstance(operation, dict) or "operationId" not in operation:
                        continue
                    operation["security"] = [{"FirebaseBearer": []}]
                    operation.setdefault("parameters", []).append(
                        {
                            "name": "X-ClassSync-Role",
                            "in": "header",
                            "required": False,
                            "description": "Select a granted workspace; verified by the server.",
                            "schema": {
                                "type": "string",
                                "enum": ["student", "teacher", "administrator"],
                            },
                        }
                    )
            app.openapi_schema = value
        return app.openapi_schema

    app.openapi = schema
