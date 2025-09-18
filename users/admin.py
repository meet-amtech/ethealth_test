# filepath: /home/dell/myprojects/EThealth_meet/ethealth/apps/users/admin.py
from django.contrib import admin
from .models import User, ClinicUser

admin.site.register(User)
admin.site.register(ClinicUser)