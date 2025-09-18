from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.base.helpers import EncryptionDecryption
from apps.base.models import Base
from ethealth import settings
from datetime import datetime, timedelta


class ClinicUserRole(models.TextChoices):
    ADMIN = 'admin', _('Admin')
    STAFF = 'staff', _('Staff')
    DOCTOR = 'doctor', _('Doctor')


class Gender(models.TextChoices):
    MALE = 'male', _('Male')
    FEMALE = 'female', _('Female')
    OTHER = 'other', _('Other')


class WeekDay(models.TextChoices):
    MONDAY = 'monday', _('Monday')
    TUESDAY = 'tuesday', _('Tuesday')
    WEDNESDAY = 'wednesday', _('Wednesday')
    THURSDAY = 'thursday', _('Thursday')
    FRIDAY = 'friday', _('Friday')
    SATURDAY = 'saturday', _('Saturday')
    SUNDAY = 'sunday', _('Sunday')


class Clinic(Base):
    name = models.CharField(max_length=255, unique=True)
    address = models.JSONField(default=dict, null=True, blank=True)
    phone_number = models.CharField(max_length=15, unique=True)
    email = models.EmailField(null=True, blank=True)
    reset_token = models.BooleanField(default=True)
    website = models.CharField(max_length=255, null=True, blank=True)
    api_key = models.CharField(max_length=255, null=True, blank=True)
    current_token_number = models.PositiveIntegerField(null=True, blank=True)
    is_accepting_requests = models.BooleanField(default=True)
    clinic_admin = models.ForeignKey('ClinicUser', on_delete=models.SET_NULL, 
                                  related_name='admin_clinic', 
                                  null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Clinic"
        verbose_name_plural = "Manage Clinics"
        ordering = ['-created_at']
        db_table = "eth_clinic"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.api_key:
            enc_data = Clinic.generate_auth_token(clinic_id=self.id)
            self.api_key = enc_data
            self.save()

    @staticmethod
    def generate_auth_token(clinic_id):
        enc_dec = EncryptionDecryption(data=clinic_id)
        return enc_dec.encryption()

    @staticmethod
    def get_default_clinic_user(clinic_id):
        try:
            clinic_user = ClinicUser.objects.filter(clinic__id=clinic_id, is_admin=True).first()
            if not clinic_user:
                clinic_user = ClinicUser.get_active_clinic_users(clinic_id=clinic_id, role=ClinicUserRole.DOCTOR).first()
            if not clinic_user:
                clinic_user = ClinicUser.get_active_clinic_users(clinic_id=clinic_id, role=ClinicUserRole.VISITING_DOCTOR).first()
            if not clinic_user:
                raise Exception("No Doctor available.")
            return clinic_user
        except ClinicUser.DoesNotExist:
            return None


class ClinicUser(Base):
    clinic = models.ForeignKey('Clinic', on_delete=models.CASCADE, related_name='clinic_users')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='clinic_user')
    role = models.CharField(max_length=255, choices=ClinicUserRole.choices, default=ClinicUserRole.STAFF)
    name = models.CharField(max_length=150, blank=True, null=True)
    address = models.JSONField(default=dict, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=255, choices=Gender.choices, blank=True, null=True)
    age = models.PositiveIntegerField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} - {self.user.phone_number}"

    class Meta:
        verbose_name = "Clinic User"
        verbose_name_plural = "Manage Clinic Users"
        ordering = ['-created_at']
        db_table = 'eth_clinic_user'
        unique_together = ['clinic', 'user']

    @staticmethod
    def get_admin_clinics(user_id):
        return ClinicUser.objects.filter(user=user_id, role=ClinicUserRole.ADMIN)

    # @staticmethod
    # def get_visitor_clinics(user_id):
    #     return ClinicUser.objects.filter(user=user_id, role=ClinicUserRole.VISITING_DOCTOR)

    @staticmethod
    def get_clinic_admins(clinic_id, user_id=None):
        filters = {'clinic_id': clinic_id, 'role': ClinicUserRole.ADMIN, 'is_active': True, 'is_deleted': False}
        if user_id:
            filters['user_id'] = user_id

        return ClinicUser.objects.filter(**filters)

    @staticmethod
    def get_active_clinic_users(clinic_id=None, user_id=None, role=None):
        filters = {'is_active': True, 'is_deleted': False}
        if clinic_id:
            filters['clinic_id'] = clinic_id
        if user_id:
            filters['user_id'] = user_id
        if role and role in ClinicUserRole.values:
            filters['role'] = role

        return ClinicUser.objects.filter(**filters)

    @staticmethod
    def get_clinic_staff(clinic_id):
        return ClinicUser.objects.filter(clinic_id=clinic_id, role=ClinicUserRole.STAFF, is_admin=False).all()


class DoctorAvailability(Base):
    """Model to manage doctor availability at clinics"""
    doctor = models.ForeignKey(
        'ClinicUser',
        on_delete=models.CASCADE,
        related_name='availability_slots',
        limit_choices_to={'role': ClinicUserRole.DOCTOR}
    )
    clinic = models.ForeignKey(
        'Clinic',
        on_delete=models.CASCADE,
        related_name='doctor_availabilities'
    )
    weekday = models.CharField(
        max_length=10,
        choices=WeekDay.choices,
        help_text="Day of the week for this availability"
    )
    start_time = models.TimeField(help_text="Start time of availability")
    end_time = models.TimeField(help_text="End time of availability")
    break_start = models.TimeField(
        null=True,
        blank=True,
        help_text="Start time of break (optional)"
    )
    break_end = models.TimeField(
        null=True,
        blank=True,
        help_text="End time of break (optional)"
    )

    class Meta:
        verbose_name = "Doctor Availability"
        verbose_name_plural = "Doctor Availabilities"
        ordering = ['doctor', 'weekday', 'start_time']
        unique_together = ['doctor', 'clinic', 'weekday']
        db_table = 'eth_doctor_availability'

    def __str__(self):
        return f"{self.doctor.name} at {self.clinic.name} on {self.weekday}"

    def clean(self):
        super().clean()
        
        # Ensure end time is after start time
        if self.end_time <= self.start_time:
            raise ValidationError({
                'end_time': 'End time must be after start time.'
            })
        
        # Validate break times if provided
        if self.break_start or self.break_end:
            if not (self.break_start and self.break_end):
                raise ValidationError({
                    'break_start': 'Both break start and end times must be provided.',
                    'break_end': 'Both break start and end times must be provided.'
                })
            
            if self.break_end <= self.break_start:
                raise ValidationError({
                    'break_end': 'Break end time must be after break start time.'
                })
            
            if not (self.start_time <= self.break_start <= self.break_end <= self.end_time):
                raise ValidationError({
                    'break_start': 'Break times must be within working hours.',
                    'break_end': 'Break times must be within working hours.'
                })
    
    # def is_available(self, time_slot):
    #     """
    #     Check if a time slot is available (not during break time)
        
    #     Args:
    #         time_slot (tuple): (start_time, end_time) as time objects
            
    #     Returns:
    #         bool: True if available, False otherwise
    #     """
    #     slot_start, slot_end = time_slot
        
    #     # Check if slot is within working hours
    #     if not (self.start_time <= slot_start.time() <= slot_end.time() <= self.end_time):
    #         return False
            
    #     # Check if slot overlaps with break time
    #     if self.break_start and self.break_end:
    #         if (slot_start.time() < self.break_end and slot_end.time() > self.break_start):
    #             return False
                
    #     return True

    # @classmethod
    # def get_available_slots(cls, doctor_id, clinic_id, date):
        """
        Get available time slots for a doctor on a specific date
        
        Args:
            doctor_id: ID of the doctor
            clinic_id: ID of the clinic
            date: Date to check availability for
            
        Returns:
            list: List of available time slots as (start_time, end_time) tuples
        """
        from datetime import timedelta
        
        weekday = date.strftime('%A').lower()
        availability = cls.objects.filter(
            doctor_id=doctor_id,
            clinic_id=clinic_id,
            weekday=weekday
        ).first()
        
        if not availability:
            return []
            
        # Generate time slots (e.g., 30-minute slots)
        slot_duration = timedelta(minutes=30)
        current_time = datetime.combine(date, availability.start_time)
        end_time = datetime.combine(date, availability.end_time)
        
        available_slots = []
        
        while current_time + slot_duration <= end_time:
            slot_end = current_time + slot_duration
            
            # Check if slot is during break time
            if not (availability.break_start and availability.break_end) or \
               not (current_time.time() < availability.break_end and slot_end.time() > availability.break_start):
                available_slots.append((current_time, slot_end))
                
            current_time = slot_end
            
        return available_slots
