def handle_initialize(request):
    response = {}
    response["protocolVersion"] = request["protocolVersion"]
    return response
