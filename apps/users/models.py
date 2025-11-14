import datetime
import logging
import random
import string

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.sessions.models import Session
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

# from ethealth.services.handle_sms import send_otp
from ethealth.settings import OTP_TIMEOUT_MINUTES

logger = logging.getLogger(__name__)


class UserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError("The Phone number must be provided")
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(phone_number, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    phone_number = models.CharField(max_length=10, unique=True, validators=[RegexValidator(
        regex=r"^\d{10}", message="Phone number must be 10 digits only.")])
    is_active = models.BooleanField(default=True)

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def save(self, *args, **kwargs):
        # Check if the password is empty
        if not self.password:
            # Use the DEFAULT_PASSWORD from settings
            self.set_password(settings.DEFAULT_PASSWORD)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.phone_number}"
        
    @property
    def is_staff(self):
            # Example: Check if user has a specific 'staff' role
            # return self.roles.filter(name='staff').exists()
            return True

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Manage Users"
        ordering = ['is_active']
        db_table = 'eth_user'

    def remove_all_active_sessions(self):
        user_sessions = []
        active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
        for session in active_sessions:
            if str(self.pk) == session.get_decoded().get('_auth_user_id'):
                user_sessions.append(session.pk)
        return Session.objects.filter(pk__in=user_sessions).delete()
        

class OTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otp')
    phone_number = models.CharField(max_length=10, validators=[RegexValidator(
        regex=r"^\d{10}", message="Phone number must be 10 digits only.")])
    otp = models.CharField(max_length=6, null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)
    otp_expiry = models.DateTimeField(blank=True, null=True)
    verification_string = models.CharField(max_length=30, null=True, blank=True)

    @classmethod
    def generate_otp(cls):
        # ToDo: Revert this change before PROD deploy
        # return f"{random.randint(100000, 999999)}"
        return 123456

    @classmethod
    def generate_verification_string(cls):
        verification_string = ''.join(random.choices(string.ascii_letters, k=16))
        timestamp = datetime.datetime.now().timestamp()
        verification_string += str(int(timestamp))
        return verification_string

    def is_valid(self):
        return self.otp_expiry > timezone.now()

    def generate_and_send_otp(self, reset_max_try=True):
        verification_string = OTP.generate_verification_string()
        otp = OTP.generate_otp()
        self.otp = otp
        self.otp_expiry = timezone.now() + datetime.timedelta(minutes=OTP_TIMEOUT_MINUTES)
        self.verification_string = verification_string
        if reset_max_try:
            self.max_otp_try = 0
        self.save()
        # send_otp(self.user.phone, otp)
        return otp, verification_string

    class Meta:
        verbose_name = "OTP"
        verbose_name_plural = "Manage OTPs"
        ordering = ['created_at']
        db_table = 'eth_otp'
