"""Team and player helper functions."""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Q

from teams.models import Member, Player


def find_members_with_name_elsewhere(name, team):
    """Return members with the same name on other teams."""
    return (
        Member.objects.filter(name=name)
        .exclude(team=team)
        .select_related('team', 'player')
        .order_by('team__name')
    )


def existing_team_names_for_member(name, team):
    """Return sorted unique team names where this member name already exists."""
    return sorted(
        find_members_with_name_elsewhere(name, team).values_list('team__name', flat=True).distinct()
    )


def resolve_player_for_api_new_member(name, team):
    """Link to an existing player when the name exists on another team; otherwise create one."""
    existing = find_members_with_name_elsewhere(name, team)
    if existing.exists():
        return existing.first().player
    return Player.objects.create(name=name)


def validate_web_member_name(name, team, member=None):
    """
    Reject member names already used on other teams (web UI must use a unique name).
    Allows keeping the current name when editing a member created via the API.
    """
    if member and member.name == name:
        return

    if find_members_with_name_elsewhere(name, team).exists():
        teams = existing_team_names_for_member(name, team)
        raise ValidationError(
            f"This name is already used in other teams ({', '.join(teams)}). "
            "Please choose a different name."
        )


def get_user_linked_player(user):
    if not user or not user.is_authenticated:
        return None
    return getattr(user, 'player_profile', None)


def is_player_claimable_by_user(player, user):
    """Return True if the user may self-claim this unlinked player."""
    if player.user_id or get_user_linked_player(user):
        return False
    username = user.username
    if player.name.lower() == username.lower():
        return True
    return player.members.filter(name__iexact=username).exists()


def get_claimable_players_for_user(user):
    """Players the user can self-claim based on matching name."""
    if get_user_linked_player(user):
        return Player.objects.none()

    username = user.username
    member_player_ids = Member.objects.filter(
        name__iexact=username,
        player__user__isnull=True,
    ).values_list('player_id', flat=True)

    return (
        Player.objects.filter(user__isnull=True)
        .filter(Q(name__iexact=username) | Q(pk__in=member_player_ids))
        .distinct()
        .prefetch_related('members__team')
        .order_by('name')
    )


def link_player_to_user(player, user):
    """Link a player profile to a user account."""
    if not user:
        raise ValidationError('User is required.')

    existing_for_user = Player.objects.filter(user=user).exclude(pk=player.pk).first()
    if existing_for_user:
        raise ValidationError(
            f"User '{user.username}' is already linked to player '{existing_for_user.name}'."
        )

    if player.user_id and player.user_id != user.id:
        raise ValidationError(
            f"Player '{player.name}' is already linked to user '{player.user.username}'."
        )

    player.user = user
    player.save(update_fields=['user', 'updated_at'])
    return player


def unlink_player_from_user(player):
    """Remove the user link from a player profile."""
    player.user = None
    player.save(update_fields=['user', 'updated_at'])
    return player


def apply_member_user_link(member, linked_username):
    """Apply or remove a user link for a member's player (admin assign)."""
    linked_username = (linked_username or '').strip()
    if linked_username:
        try:
            user = User.objects.get(username=linked_username)
        except User.DoesNotExist as exc:
            raise ValidationError(f"User '{linked_username}' does not exist.") from exc
        link_player_to_user(member.player, user)
    elif member.player.user_id:
        unlink_player_from_user(member.player)
