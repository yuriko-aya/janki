"""
Custom authentication classes for the API.
"""
from rest_framework.authentication import TokenAuthentication


class BearerTokenAuthentication(TokenAuthentication):
    """
    Bearer token authentication.
    
    Uses "Bearer" keyword instead of "Token" in the Authorization header.
    Header format: Authorization: Bearer <token>
    """
    keyword = 'Bearer'
