"""
Serializers for Teams REST API.
"""
from rest_framework import serializers
from teams.models import Member


class MemberSerializer(serializers.Serializer):
    """Serializer for creating a new member."""
    name = serializers.CharField(max_length=100, required=True)
    confirm_same_player = serializers.BooleanField(required=False, allow_null=True, default=None)

    def validate_name(self, value):
        """Validate that member name is not empty and doesn't already exist in team."""
        if not value or not value.strip():
            raise serializers.ValidationError("Member name cannot be empty")
        
        team = self.context.get('team')
        if not team:
            raise serializers.ValidationError("Team context is required")
        
        # Check if member with this name already exists in the team
        if Member.objects.filter(name=value, team=team).exists():
            raise serializers.ValidationError(
                f"Member '{value}' already exists in team {team.name}"
            )
        
        return value.strip()
