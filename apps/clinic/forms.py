from django import forms
from .models import Clinic, DoctorAvailability, WeekDay
from .models import WeekDay


class ClinicDetailsForm(forms.ModelForm):
    """Form for managing clinic details"""
    
    # Address fields
    address_line1 = forms.CharField(
        max_length=255, 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Street Address'})
    )
    address_city = forms.CharField(
        max_length=100, 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City'})
    )
    address_state = forms.CharField(
        max_length=100, 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'State/Province'})
    )
    address_country = forms.CharField(
        max_length=100, 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Country'})
    )
    address_postal_code = forms.CharField(
        max_length=20, 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Postal Code'})
    )
    
    class Meta:
        model = Clinic
        fields = ['name', 'phone_number', 'email', 'reset_token', 'website', 'api_key']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Clinic Name'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
            'reset_token': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Website URL'}),
            'api_key': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly', 'placeholder': 'API Key (Read-only)'}),
        }
        labels = {
            'name': 'Clinic Name',
            'phone_number': 'Phone Number',
            'email': 'Email Address',
            'reset_token': 'Reset Token',
            'website': 'Website URL',
            'api_key': 'API Key',
        }
    
    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)
        
        # Populate address fields from JSON field
        if instance and instance.address:
            self.fields['address_line1'].initial = instance.address.get('line1', '')
            self.fields['address_city'].initial = instance.address.get('city', '')
            self.fields['address_state'].initial = instance.address.get('state', '')
            self.fields['address_country'].initial = instance.address.get('country', '')
            self.fields['address_postal_code'].initial = instance.address.get('postal_code', '')
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Handle address fields
        address = {}
        address_fields = ['line1', 'city', 'state', 'country', 'postal_code']
        
        for field in address_fields:
            form_field = f'address_{field}'
            field_value = self.cleaned_data.get(form_field, '').strip()
            if field_value:
                address[field] = field_value
        
        # Only save address if at least one field has a value, otherwise save empty dict
        instance.address = address if any(address.values()) else {}
        
        # Prevent api_key from being modified through the form
        if hasattr(instance, '_state') and instance._state.adding is False:
            # For existing instances, preserve the original api_key
            original_instance = Clinic.objects.get(pk=instance.pk)
            instance.api_key = original_instance.api_key
        
        if commit:
            instance.save()
        return instance

    def clean(self):
        cleaned_data = super().clean()
        # Add any custom validation here
        return cleaned_data

class OpeningHourForm(forms.Form):
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        required=True
    )
    end_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        required=True
    )
    break_start = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        required=False
    )
    break_end = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        required=False
    )
    selected_days = forms.MultipleChoiceField(
        choices=WeekDay.choices,
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}),
        required=True
    )

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        break_start = cleaned_data.get('break_start')
        break_end = cleaned_data.get('break_end')

        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError("End time must be after start time.")

        if (break_start and not break_end) or (not break_start and break_end):
            raise forms.ValidationError("Please provide both break start and end times or leave both empty.")

        if break_start and break_end:
            if not (start_time <= break_start <= break_end <= end_time):
                raise forms.ValidationError("Break time must be within working hours.")

        return cleaned_data