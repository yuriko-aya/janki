from django import forms
from teams.models import Team, Member


class TeamForm(forms.ModelForm):
    """Form for creating and updating a Team."""
    
    class Meta:
        model = Team
        fields = ['name', 'start_point', 'target_point', 'uma_first', 'uma_second', 'uma_third', 'uma_fourth', 'chombo_enabled']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter team name'
            }),
            'start_point': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '30000'
            }),
            'target_point': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '30000'
            }),
            'uma_first': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '+15'
            }),
            'uma_second': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '+5'
            }),
            'uma_third': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '-5'
            }),
            'uma_fourth': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '-15'
            }),
            'chombo_enabled': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }
        labels = {
            'start_point': 'Starting Chips',
            'target_point': 'Target Score (for base calculation)',
            'uma_first': '1st Place Uma',
            'uma_second': '2nd Place Uma',
            'uma_third': '3rd Place Uma',
            'uma_fourth': '4th Place Uma',
            'chombo_enabled': 'Enable Chombo Penalty (-30 points)',
        }


class MemberForm(forms.ModelForm):
    """Form for creating and updating a Team Member."""
    
    class Meta:
        model = Member
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter member name'
            }),
        }
