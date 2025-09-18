from django.contrib import admin

from .models import Clinic, ClinicUser, DoctorAvailability


admin.site.register(Clinic)
admin.site.register(ClinicUser)

@admin.register(DoctorAvailability)
class DoctorAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'clinic', 'weekday', 'start_time', 'end_time', 'has_break')
    list_filter = ('weekday', 'clinic', 'doctor')
    search_fields = ('doctor__name', 'clinic__name')
    ordering = ('weekday', 'start_time')
    
    def has_break(self, obj):
        return bool(obj.break_start and obj.break_end)
    has_break.boolean = True
    has_break.short_description = 'Has Break'
