import jwt

EXPECTED_AUDIENCE = "https://mcp.example.com"


def authenticate(request):
    token = request.headers["Authorization"].removeprefix("Bearer ")
    claims = jwt.decode(token, PUBLIC_KEY, algorithms=["RS256"], audience=EXPECTED_AUDIENCE)
    return claims["sub"]
