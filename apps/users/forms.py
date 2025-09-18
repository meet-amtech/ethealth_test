from django import forms
from apps.clinic.models import ClinicUser

class UserProfileForm(forms.ModelForm):
    phone_number = forms.CharField(max_length=10)
    address = forms.JSONField(required=False)

    class Meta:
        model = ClinicUser
        fields = ['name', 'address', 'date_of_birth', 'gender', 'age']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['phone_number'].initial = self.instance.user.phone_number
            # self.fields['address'].initial = self.instance.user.address