from django import forms

from taikai.models import Tournament, TournamentMember
from taikai.services.calculator import get_standing_totals


def member_choices_by_standings(tournament, *, finals_only=False):
    """Build member dropdown choices sorted by standing total (substitutes last)."""
    totals = get_standing_totals(tournament)
    if finals_only and tournament.finals_cutoff:
        members = list(tournament.finals_members())
    else:
        members = list(tournament.roster_members())

    def sort_key(member):
        if member.is_substitute:
            return (1, member.name.lower())
        if finals_only and not member.in_finals:
            return (2, member.name.lower())
        data = totals.get(member.id, {'total': 0.0, 'games': 0})
        return (0, -data['total'], -data['games'], member.name.lower())

    members.sort(key=sort_key)
    choices = []
    for member in members:
        if member.is_substitute:
            label = f'{member.shown_name} (sub)'
        else:
            data = totals.get(member.id, {'total': 0.0, 'games': 0})
            label = f'{member.shown_name} ({data["total"]:+.1f})'
        choices.append((member.id, label))
    return choices


class TournamentForm(forms.ModelForm):
    class Meta:
        model = Tournament
        fields = [
            'name', 'start_point', 'target_point',
            'uma_first', 'uma_second', 'uma_third', 'uma_fourth',
            'chombo_enabled', 'chombo_penalty', 'session_mode',
            'fixed_hanchan_count', 'hidden',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'start_point': forms.NumberInput(attrs={'class': 'form-control'}),
            'target_point': forms.NumberInput(attrs={'class': 'form-control'}),
            'uma_first': forms.NumberInput(attrs={'class': 'form-control'}),
            'uma_second': forms.NumberInput(attrs={'class': 'form-control'}),
            'uma_third': forms.NumberInput(attrs={'class': 'form-control'}),
            'uma_fourth': forms.NumberInput(attrs={'class': 'form-control'}),
            'chombo_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'chombo_penalty': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'session_mode': forms.Select(attrs={'class': 'form-control', 'id': 'id_session_mode'}),
            'fixed_hanchan_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'id': 'id_fixed_hanchan_count'}),
            'hidden': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fixed_hanchan_count'].help_text = (
            'Number of fixed hanchans (fixed and hybrid modes only). '
            'Rank hanchans are added one at a time after scores are entered.'
        )
        self.fields['chombo_penalty'].help_text = (
            'Raw score deducted per chombo (default 30000 = -30 pts after ÷1000).'
        )


class TournamentMemberForm(forms.ModelForm):
    class Meta:
        model = TournamentMember
        fields = ['name', 'display_name', 'is_substitute']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Member name'}),
            'display_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional display name'}),
            'is_substitute': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.tournament = kwargs.pop('tournament', None)
        if self.tournament is None and kwargs.get('instance') is not None:
            self.tournament = kwargs['instance'].tournament
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data.get('name', '')
        if ' ' in name:
            raise forms.ValidationError('Member name cannot contain spaces.')
        tournament = self.tournament
        if tournament is None and self.instance.pk:
            tournament = self.instance.tournament
        if tournament and TournamentMember.objects.filter(
            tournament=tournament,
            name=name,
        ).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(
                f'A member named "{name}" already exists in this tournament.'
            )
        return name


class GenerateSessionsForm(forms.Form):
    confirm = forms.BooleanField(
        required=True,
        label='Regenerate fixed sessions (existing sessions and scores will be deleted, standings reset)',
    )


class FinalsCutoffForm(forms.Form):
    cutoff = forms.IntegerField(
        min_value=4,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': 4,
            'step': 4,
            'style': 'width: 5rem; padding: 0.35rem 0.5rem;',
            'placeholder': '8',
        }),
        help_text='Top N players (must be divisible by 4)',
    )

    def clean_cutoff(self):
        cutoff = self.cleaned_data['cutoff']
        if cutoff % 4 != 0:
            raise forms.ValidationError('Cutoff must be divisible by 4 (tables seat 4 players).')
        return cutoff


class ManualSessionForm(forms.Form):
    """Create a single session by selecting four players."""

    seat_count = 4

    def __init__(self, tournament, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tournament = tournament
        finals_only = bool(tournament.finals_cutoff)
        choices = member_choices_by_standings(tournament, finals_only=finals_only)
        for i in range(self.seat_count):
            self.fields[f'member_{i}'] = forms.ChoiceField(
                choices=choices,
                label=f'Seat {i + 1} — Player',
                widget=forms.Select(attrs={'class': 'form-control'}),
            )

    def clean(self):
        cleaned = super().clean()
        if any(self.errors):
            return cleaned
        member_ids = [int(cleaned[f'member_{i}']) for i in range(self.seat_count)]
        if len(set(member_ids)) != self.seat_count:
            raise forms.ValidationError('Each seat must have a different player.')
        valid_ids = set(self.tournament.members.values_list('id', flat=True))
        if not set(member_ids).issubset(valid_ids):
            raise forms.ValidationError('All players must be tournament members.')
        if self.tournament.finals_cutoff:
            finals_ids = set(self.tournament.finals_members().values_list('id', flat=True))
            if not set(member_ids).issubset(finals_ids):
                raise forms.ValidationError('All players must be in the finals cutoff group.')
        return cleaned

    def get_member_ids(self):
        return [int(self.cleaned_data[f'member_{i}']) for i in range(self.seat_count)]


class AddTournamentAdminForm(forms.Form):
    """Form for adding a new admin to a tournament."""
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter username to add as admin',
        }),
        help_text='Enter the username of the user you want to add as a tournament admin.',
    )

    def __init__(self, *args, **kwargs):
        self.tournament = kwargs.pop('tournament', None)
        super().__init__(*args, **kwargs)

    def clean_username(self):
        from django.contrib.auth.models import User
        from taikai.models import TournamentAdmin

        username = self.cleaned_data.get('username')
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise forms.ValidationError(f"User '{username}' does not exist.")

        if self.tournament and TournamentAdmin.objects.filter(
            tournament=self.tournament, user=user
        ).exists():
            raise forms.ValidationError(
                f"User '{username}' is already an admin of this tournament."
            )

        return username


class TournamentSessionScoreForm(forms.Form):
    """Dynamic form for 4 seats: player selection, raw score, and chombo."""

    def __init__(self, session, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = session
        self.seat_count = 4
        scores = list(session.scores.select_related('member').order_by('pk'))
        member_choices = member_choices_by_standings(session.tournament)
        for i, score_obj in enumerate(scores):
            self.fields[f'member_{i}'] = forms.ChoiceField(
                choices=member_choices,
                initial=score_obj.member_id,
                label=f'Seat {i + 1} — Player',
                widget=forms.Select(attrs={'class': 'form-control'}),
            )
            self.fields[f'score_{i}'] = forms.IntegerField(
                initial=score_obj.score,
                label=f'Seat {i + 1} — Raw score',
                widget=forms.NumberInput(attrs={'class': 'form-control'}),
            )
            if session.tournament.chombo_enabled:
                self.fields[f'chombo_{i}'] = forms.IntegerField(
                    initial=score_obj.chombo,
                    required=False,
                    label=f'Seat {i + 1} — Chombo',
                    widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
                )

    def clean(self):
        cleaned = super().clean()
        if any(self.errors):
            return cleaned
        member_ids = [int(cleaned[f'member_{i}']) for i in range(self.seat_count)]
        if len(set(member_ids)) != self.seat_count:
            raise forms.ValidationError('Each seat must have a different player.')
        valid_ids = set(
            self.session.tournament.members.values_list('id', flat=True)
        )
        if not set(member_ids).issubset(valid_ids):
            raise forms.ValidationError('All players must be tournament members.')
        return cleaned

    def get_score_data(self):
        data = []
        for i in range(self.seat_count):
            data.append({
                'member_id': int(self.cleaned_data[f'member_{i}']),
                'score': self.cleaned_data[f'score_{i}'],
                'chombo': self.cleaned_data.get(f'chombo_{i}', 0) or 0,
            })
        return data
