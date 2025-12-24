"""
Serializers for REST API score submission.
"""
from rest_framework import serializers
from scores.models import RawScore
from teams.models import Member


class ScoreEntrySerializer(serializers.Serializer):
    """Serializer for a single score entry within a session."""
    member_name = serializers.CharField(required=True)
    score = serializers.IntegerField(required=True)
    chombo = serializers.IntegerField(required=False, default=0, min_value=0)
    
    def validate_member_name(self, value):
        """Validate that member exists and belongs to the team."""
        team = self.context.get('team')
        if not team:
            raise serializers.ValidationError("Team context is required")
        
        try:
            member = Member.objects.get(name=value, team=team)
        except Member.DoesNotExist:
            raise serializers.ValidationError(
                f"Member '{value}' does not exist in team {team.name}"
            )
        
        return value


class SessionScoresSerializer(serializers.Serializer):
    """Serializer for submitting all scores for a session."""
    session_id = serializers.CharField(max_length=100, required=True)
    session_date = serializers.DateField(required=False, allow_null=True)
    scores = ScoreEntrySerializer(many=True, required=True)
    
    def validate_scores(self, value):
        """Validate that exactly 4 scores are provided."""
        if len(value) != 4:
            raise serializers.ValidationError(
                f"Exactly 4 scores are required for a session, got {len(value)}"
            )
        
        # Check for duplicate members
        member_names = [score['member_name'] for score in value]
        if len(member_names) != len(set(member_names)):
            raise serializers.ValidationError(
                "Each member can only appear once per session"
            )
        
        # Validate each score entry with team context
        team = self.context.get('team')
        for score_data in value:
            score_serializer = ScoreEntrySerializer(
                data=score_data,
                context={'team': team}
            )
            score_serializer.is_valid(raise_exception=True)
        
        return value
