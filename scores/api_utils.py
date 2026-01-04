"""
Utility functions for API responses to reduce duplication.
"""
from rest_framework import status
from rest_framework.response import Response


def success_response(message, data=None, status_code=status.HTTP_200_OK):
    """
    Create a standardized success response.
    
    Args:
        message: Success message string
        data: Optional dict of additional data to include
        status_code: HTTP status code (default 200)
        
    Returns:
        Response object
    """
    response_data = {'success': True, 'message': message}
    if data:
        response_data.update(data)
    return Response(response_data, status=status_code)


def error_response(message, status_code=status.HTTP_400_BAD_REQUEST):
    """
    Create a standardized error response.
    
    Args:
        message: Error message string
        status_code: HTTP status code (default 400)
        
    Returns:
        Response object
    """
    return Response({'error': message}, status=status_code)


def permission_denied_response(message="You do not have permission to perform this action."):
    """
    Create a standardized permission denied response.
    
    Args:
        message: Error message string (default generic message)
        
    Returns:
        Response object with 403 Forbidden status
    """
    return error_response(message, status.HTTP_403_FORBIDDEN)


def not_found_response(message):
    """
    Create a standardized not found response.
    
    Args:
        message: Error message string
        
    Returns:
        Response object with 404 Not Found status
    """
    return error_response(message, status.HTTP_404_NOT_FOUND)


def validation_error_response(errors):
    """
    Create a standardized validation error response.
    
    Args:
        errors: Dict or list of validation errors
        
    Returns:
        Response object with 400 Bad Request status
    """
    if isinstance(errors, dict):
        return Response({'success': False, 'errors': errors}, status=status.HTTP_400_BAD_REQUEST)
    else:
        return error_response(str(errors), status.HTTP_400_BAD_REQUEST)
