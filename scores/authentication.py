"""
Custom authentication classes for the API.
"""
from drf_multitokenauth.coreauthentication import MultiTokenAuthentication


class BearerMultiTokenAuthentication(MultiTokenAuthentication):
    """
    Bearer token authentication using drf-multitokenauth.
    
    Uses "Bearer" keyword instead of "Token" in the Authorization header.
    Header format: Authorization: Bearer <token>
    
    Supports multiple tokens per user.
    """
    keyword = 'Bearer'
