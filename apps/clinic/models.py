from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.base.helpers import EncryptionDecryption
from apps.base.models import Base
from ethealth import settings


class ClinicUserRole(models.TextChoices):
    ADMIN = 'admin', _('Admin')
    STAFF = 'staff', _('Staff')


class Gender(models.TextChoices):
    MALE = 'male', _('Male')
    FEMALE = 'female', _('Female')
    OTHER = 'other', _('Other')


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
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='clinic_users')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='clinic_users')
    role = models.CharField(max_length=255, choices=ClinicUserRole.choices, default=ClinicUserRole.STAFF)
    name = models.CharField(max_length=150, blank=True, null=True)
    address = models.JSONField(default=dict, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=255, choices=Gender.choices, blank=True, null=True)
    age = models.PositiveIntegerField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} - {self.clinic.name}"

    class Meta:
        verbose_name = "Clinic User"
        verbose_name_plural = "Manage Clinic Users"
        ordering = ['-created_at']
        db_table = 'eth_clinic_user'
        unique_together = ['clinic', 'user']

    @staticmethod
    def get_admin_clinics(user_id):
        return ClinicUser.objects.filter(user=user_id, is_admin=True)

    @staticmethod
    def get_visitor_clinics(user_id):
        return ClinicUser.objects.filter(user=user_id, role=ClinicUserRole.VISITING_DOCTOR)

    @staticmethod
    def get_clinic_admins(clinic_id, user_id=None):
        filters = {'clinic_id': clinic_id, 'is_admin': True}
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


