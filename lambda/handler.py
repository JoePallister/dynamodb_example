import json
import boto3
import os
from datetime import datetime
from boto3.dynamodb.conditions import Key
import uuid
from datetime import datetime


# -----------------------------
# DynamoDB setup
# -----------------------------
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])


# -----------------------------
# Response helper
# -----------------------------
def response(status, body):
    return {
        "statusCode": status,
        "body": json.dumps(body),
    }


def generate_id():
    return f"{datetime.utcnow().isoformat()}-{uuid.uuid4()}"


# -----------------------------
# Validation
# -----------------------------
def validate_body(body):
    if "version" not in body:
        return "missing version"

    if "enabled" not in body:
        return "missing enabled"

    if not isinstance(body["version"], str):
        return "version must be string"

    if not isinstance(body["enabled"], bool):
        return "enabled must be boolean"

    return None


# -----------------------------
# Create release (immutable write)
# -----------------------------
def create_release(service, body):
    error = validate_body(body)
    if error:
        return response(400, {"error": error})

    version_id = generate_id()

    item = {
        "service": service,
        "version_id": version_id,
        "version": body["version"],
        "enabled": body["enabled"],
        "created_at": datetime.utcnow().isoformat(),
    }

    table.put_item(Item=item)

    return response(200, {"message": "release created", "item": item})


# -----------------------------
# Get latest release
# -----------------------------
def get_latest_release(service):
    resp = table.query(
        KeyConditionExpression=Key("service").eq(service),
        ScanIndexForward=False,  # newest first (by ULID)
        Limit=1,
    )

    items = resp.get("Items", [])

    if not items:
        return response(404, {"error": "not found"})

    return response(200, items[0])


# -----------------------------
# Rollback (to previous version)
# -----------------------------
def rollback_release(service):
    resp = table.query(
        KeyConditionExpression=Key("service").eq(service),
        ScanIndexForward=False,
        Limit=2,
    )

    items = resp.get("Items", [])

    if len(items) < 2:
        return response(400, {"error": "no previous version to rollback to"})

    current = items[0]
    previous = items[1]

    rollback_item = {
        "service": service,
        "version_id": generate_id(),
        "version": previous["version"],
        "enabled": True,
        "created_at": datetime.utcnow().isoformat(),
    }

    table.put_item(Item=rollback_item)

    return response(
        200,
        {
            "message": "rolled back",
            "from": current["version"],
            "to": previous["version"],
        },
    )


# -----------------------------
# Router
# -----------------------------
def lambda_handler(event, context):

    service = event["pathParameters"]["service"]
    method = event["requestContext"]["http"]["method"]
    path = event.get("rawPath", "")

    print(json.dumps(event))

    # GET /releases/{service}
    if method == "GET":
        return get_latest_release(service)

    # POST /releases/{service}/rollback
    if method == "POST" and path.endswith("/rollback"):
        return rollback_release(service)

    # POST /releases/{service}
    if method == "POST":
        body = json.loads(event.get("body", "{}"))
        return create_release(service, body)

    return response(405, {"error": "method not allowed"})
