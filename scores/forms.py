from django import forms
from scores.models import RawScore


class RawScoreForm(forms.ModelForm):
    """Form for submitting a RawScore."""
    
    class Meta:
        model = RawScore
        fields = ['member', 'score', 'chombo', 'session_id']
        widgets = {
            'member': forms.Select(attrs={'class': 'form-control'}),
            'score': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter score (e.g., 25000)'
            }),
            'chombo': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'value': '0',
            }),
            'session_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Session ID'
            }),
        }


class SessionScoresForm(forms.Form):
    """Form for submitting all 4 scores for a session at once."""
    session_id = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Session ID'
        })
    )
    session_date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
        }),
        label='Session Date',
        help_text='Date of the game session'
    )
    
    def __init__(self, team, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.team = team
        
        # Add 4 score fields dynamically
        members = team.members.all()
        for i in range(4):
            self.fields[f'member_{i}'] = forms.ModelChoiceField(
                queryset=members,
                widget=forms.Select(attrs={'class': 'form-control'}),
                label=f'Player {i + 1}'
            )
            self.fields[f'score_{i}'] = forms.IntegerField(
                widget=forms.NumberInput(attrs={
                    'class': 'form-control',
                    'placeholder': f'Score for Player {i + 1}'
                }),
                label=f'Score {i + 1}'
            )
            self.fields[f'chombo_{i}'] = forms.IntegerField(
                required=False,
                initial=0,
                widget=forms.NumberInput(attrs={
                    'class': 'form-control',
                    'min': '0',
                    'value': '0',
                }),
                label=f'Chombo Count (Player {i + 1})'
            )


class SessionEditForm(SessionScoresForm):
    """Form for editing existing session scores."""
    
    def __init__(self, team, session_id, *args, **kwargs):
        super().__init__(team, *args, **kwargs)
        self.session_id = session_id
        
        # Make session_id read-only since we're editing
        self.fields['session_id'].widget.attrs['readonly'] = True
        self.fields['session_id'].initial = session_id
