SUPPORTED_VERSIONS = ["2025-11-25", "2025-06-18"]


def handle_initialize(request):
    requested = request["protocolVersion"]
    negotiated = requested if requested in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
    return {"protocolVersion": negotiated}
