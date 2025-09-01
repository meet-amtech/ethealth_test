from django.contrib import admin

from .models import Clinic, ClinicUser


admin.site.register(Clinic)
admin.site.register(ClinicUser)
