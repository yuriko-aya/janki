from django import forms

from taikai.models import Tournament, TournamentMember


class TournamentForm(forms.ModelForm):
    class Meta:
        model = Tournament
        fields = [
            'name', 'start_point', 'target_point',
            'uma_first', 'uma_second', 'uma_third', 'uma_fourth',
            'chombo_enabled', 'session_mode',
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


class TournamentMemberForm(forms.ModelForm):
    class Meta:
        model = TournamentMember
        fields = ['name', 'display_name', 'is_substitute']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Member name'}),
            'display_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional display name'}),
            'is_substitute': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '')
        if ' ' in name:
            raise forms.ValidationError('Member name cannot contain spaces.')
        return name


class GenerateSessionsForm(forms.Form):
    confirm = forms.BooleanField(
        required=True,
        label='Regenerate fixed sessions (existing sessions and scores will be deleted, standings reset)',
    )


class TournamentSessionScoreForm(forms.Form):
    """Dynamic form for 4 seats: player selection, raw score, and chombo."""

    def __init__(self, session, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = session
        self.seat_count = 4
        scores = list(session.scores.select_related('member').order_by('pk'))
        member_choices = [
            (
                m.id,
                f"{m.shown_name}{' (sub)' if m.is_substitute else ''}",
            )
            for m in session.tournament.roster_members()
        ]
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
