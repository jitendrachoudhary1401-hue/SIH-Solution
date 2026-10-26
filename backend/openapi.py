"""Generate the API inventory and validated mutation schemas from the application."""
import json
from pathlib import Path
from app import create_app
from app.api import Registration, OrdinaryChange, StatusChange, ActionChange, TransferChange, ReviewChange, Change

app = create_app()
schemas = [Registration, OrdinaryChange, StatusChange, ActionChange, TransferChange, ReviewChange, Change]
request_models = {"api.register_case": "Registration", "api.edit_case": "OrdinaryChange", "api.change_status": "StatusChange",
                  "api.add_action": "ActionChange", "api.transfer": "TransferChange", "api.review": "ReviewChange", "api.sla_clock": "Change"}
document = {"openapi": "3.1.0", "info": {"title": "OneCase API", "version": "1.0.0", "description": "Officer workspace API. Mutations require a same-origin request and X-CSRF-Token returned by auth/me or login."},
            "paths": {}, "components": {"schemas": {s.__name__: s.model_json_schema() for s in schemas},
            "securitySchemes": {"officerSession": {"type": "apiKey", "in": "cookie", "name": "onecase_session"}}}}
for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
    if not rule.rule.startswith("/api/"):
        continue
    path = rule.rule
    parameters = []
    for name in rule.arguments:
        start = path.index("<")
        end = path.index(">", start)
        token = path[start:end + 1]
        parameter = token.strip("<>").split(":")[-1]
        path = path.replace(token, "{" + parameter + "}")
        parameters.append({"name": parameter, "in": "path", "required": True, "schema": {"type": "integer" if "int:" in token else "string"}})
    methods = {}
    for method in sorted(rule.methods - {"OPTIONS", "HEAD"}):
        operation = {"operationId": rule.endpoint.replace(".", "_") + "_" + method.lower(), "summary": rule.endpoint.split(".")[-1].replace("_", " "),
                     "responses": {"200": {"description": "Success; list endpoints return items, total, nextCursor and asOf"}, "401": {"description": "Missing or expired session"}, "403": {"description": "Forbidden or invalid CSRF token"}, "404": {"description": "Resource unavailable in authorized scope"}, "409": {"description": "Stale version or concurrent mutation"}, "422": {"description": "Invalid request"}}, "parameters": parameters}
        if rule.endpoint not in ("api.login", "health"):
            operation["security"] = [{"officerSession": []}]
        if rule.endpoint in request_models:
            operation["requestBody"] = {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/" + request_models[rule.endpoint]}}}}
        if rule.endpoint == "api.register_case":
            operation["parameters"].append({"name": "Idempotency-Key", "in": "header", "required": True, "schema": {"type": "string", "minLength": 8, "maxLength": 100}})
            operation["responses"]["201"] = {"description": "Registered complaint"}
        methods[method.lower()] = operation
    document["paths"][path] = methods
Path("docs").mkdir(exist_ok=True)
Path("docs/openapi.json").write_text(json.dumps(document, indent=2), encoding="utf-8")
print("API contract written to docs/openapi.json")
