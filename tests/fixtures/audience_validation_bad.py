import jwt


def authenticate(request):
    token = request.headers["Authorization"].removeprefix("Bearer ")
    claims = jwt.decode(token, PUBLIC_KEY, algorithms=["RS256"])
    return claims["sub"]
