from django.contrib import admin
from apps.appointment.models import Patient, ClinicPatient, AppointmentRequest, Appointment


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['name',  'date_of_birth', 'user', 'is_active', 'created_at']
    list_filter = ['is_active', 'is_deleted', 'created_at']
    search_fields = ['name']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(ClinicPatient)
class ClinicPatientAdmin(admin.ModelAdmin):
    list_display = ['patient', 'clinic', 'is_active', 'created_at']
    list_filter = ['clinic', 'is_active', 'is_deleted', 'created_at']
    search_fields = ['patient__name', 'clinic__name']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(AppointmentRequest)
class AppointmentRequestAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'clinic', 'request_token', 'appointment_request_status', 'confirmed_at', 'created_at']
    list_filter = ['appointment_request_status', 'clinic', 'gender', 'is_active', 'created_at']
    search_fields = ['name', 'phone', 'request_token']
    readonly_fields = ['id', 'created_at', 'updated_at', 'confirmed_at']


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['clinic_patient', 'doctor', 'appointment_date', 'appointment_time', 'appointment_status', 'paid', 'created_at']
    list_filter = ['appointment_status', 'paid', 'appointment_date', 'is_active', 'created_at']
    search_fields = ['clinic_patient__patient__name', 'doctor__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'appointment_date'
