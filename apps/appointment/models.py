import logging
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from apps.base.models import Base
from apps.users.models import User 
from apps.clinic.models import Clinic, ClinicUser, ClinicUserRole, Gender
from ethealth import settings

logger = logging.getLogger(__name__)


class AppointmentRequestStatus(models.TextChoices):
    PENDING = 'pending', _('Pending')
    CONFIRMED = 'confirmed', _('Confirmed')
    CANCELLED = 'cancelled', _('Cancelled')


class AppointmentStatus(models.TextChoices):
    SCHEDULED = 'scheduled', _('Scheduled')
    IN_PROGRESS = 'in_progress', _('In Progress')
    COMPLETED = 'completed', _('Completed')
    CANCELLED = 'cancelled', _('Cancelled')


class Patient(Base):
    """Model to store patient information"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='patients',
        null=True,
        blank=True,
        help_text="Link to user account if patient has one"
    )
    name = models.CharField(max_length=150)
    age = models.PositiveIntegerField(null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    phone_number = models.CharField(
        max_length=10,
        validators=[RegexValidator(
            regex=r"^\d{10}",
            message="Phone number must be 10 digits only."
        )]
    )

    def __str__(self):
        return f"{self.name}"

    class Meta:
        verbose_name = "Patient"
        verbose_name_plural = "Manage Patients"
        ordering = ['-created_at']
        db_table = 'eth_patient'

    @staticmethod
    def create_patient(user, name, phone_number, age=0, date_of_birth=None):
        patient = self.Meta.model.filter(user=user).first()
        if patient:
            return patient
        return Patient.objects.create(user=user,name=name,age=age,date_of_birth=date_of_birth,phone_number=phone_number)


class ClinicPatient(Base):
    """Model to link patients to specific clinics"""
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name='clinic_patients'
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='clinic_associations'
    )

    def __str__(self):
        return f"{self.patient.name} at {self.clinic.name}"

    class Meta:
        verbose_name = "Clinic Patient"
        verbose_name_plural = "Manage Clinic Patients"
        ordering = ['-created_at']
        db_table = 'eth_clinic_patient'
        unique_together = ['clinic', 'patient']

    @staticmethod
    def create_clinic_patient(patient, clinic):
        if not isinstance(patient, Patient):
            logger.error("Invalid patient instance provided.")
            raise ValueError("Invalid patient instance provided.")
        if not isinstance(clinic, Clinic):
            logger.error("Invalid clinic instance provided.")
            raise ValueError("Invalid clinic instance provided.")

        # Check if the clinic patient already exists
        existing_clinic_patient = ClinicPatient.objects.filter(patient=patient, clinic=clinic).first()
        if existing_clinic_patient:
            logger.info("Clinic patient already exists.")
            return existing_clinic_patient

        # Create the ClinicPatient instance
        clinic_patient = ClinicPatient.objects.create(
            patient=patient,
            clinic=clinic
        )
        return clinic_patient



class AppointmentRequest(Base):
    """Model to handle appointment requests from patients"""
    name = models.CharField(max_length=150)
    phone = models.CharField(
        max_length=10,
        validators=[RegexValidator(
            regex=r"^\d{10}",
            message="Phone number must be 10 digits only."
        )]
    )
    age = models.PositiveIntegerField(null=True, blank=True)
    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        blank=True,
        null=True
    )
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name='appointment_requests'
    )
    request_token = models.PositiveIntegerField(
        help_text="Token number for the appointment request"
    )
    appointment_request_status = models.CharField(
        max_length=15,
        choices=AppointmentRequestStatus.choices,
        default=AppointmentRequestStatus.PENDING,
        help_text="Status of the appointment request"
    )
    source = models.TextField(
        blank=True,
        null=True,
        default='dashboard',
        help_text="Source of the appointment request (e.g., dashboard, API, phone)"
    )
    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the request was confirmed"
    )
    expired_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the request expires"
    )

    def __str__(self):
        return f"{self.name} - {self.phone} - Token: {self.request_token} - {self.clinic.name}"

    def generate_next_request_token(self):
        """Generate the next token number for this clinic"""
        if not self.clinic.is_active:
            logger.error("The clinic is not active.")
            raise ValueError("The clinic is not active.")

        # Reset token if clinic has reset_token flag set
        if self.clinic.reset_token:
            self.clinic.reset_token = False
            self.clinic.save()
            return 1

        # Get the last token for this clinic
        last_request = AppointmentRequest.objects.filter(
            clinic_id=self.clinic_id
        ).order_by('-created_at').first()

        if last_request:
            return last_request.request_token + 1

        return 1

    def _confirm_appointment(self):
        """
        Creates  User, Patient, ClinicPatient, and Appointment records
        when the request status is 'confirmed'.
        """
        with transaction.atomic():
            user, _ = User.objects.get_or_create(phone_number=self.phone)

            patient, _ = Patient.objects.get_or_create(
                phone_number=self.phone,
                name=self.name
            )

            clinic_patient, _ = ClinicPatient.objects.get_or_create(
                clinic_id=self.clinic_id,
                patient=patient
            )

            Appointment.objects.get_or_create(
                appointment_request=self,
                defaults={
                    'clinic_patient': clinic_patient,
                    'appointment_status': AppointmentStatus.SCHEDULED,
                    'appointment_date': self.confirmed_at.date(),
                    'appointment_time': self.confirmed_at.time(),
                }
            )

    def save(self, *args, **kwargs):
        # Auto-generate token if not set
        if not self.request_token:
            self.request_token = self.generate_next_request_token()
        
        if self.pk and self.appointment_request_status == AppointmentRequestStatus.CONFIRMED:
            self._confirm_appointment()

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Appointment Request"
        verbose_name_plural = "Manage Appointment Requests"
        ordering = ['-created_at']
        db_table = 'eth_appointment_request'


class Appointment(Base):
    """Model to store confirmed appointments"""
    clinic_patient = models.ForeignKey(
        ClinicPatient,
        on_delete=models.CASCADE,
        related_name='appointments'
    )
    appointment_request = models.ForeignKey(
        AppointmentRequest,
        on_delete=models.SET_NULL,
        related_name='appointments',
        null=True,
        blank=True,
        help_text="Link to the original appointment request"
    )
    doctor = models.ForeignKey(
        ClinicUser,
        on_delete=models.SET_NULL,
        related_name='appointments',
        null=True,
        blank=True,
        limit_choices_to=Q(role=ClinicUserRole.DOCTOR) | Q(role=ClinicUserRole.ADMIN)
    )
    appointment_date = models.DateField(help_text="Date of the appointment")
    appointment_time = models.TimeField(help_text="Time of the appointment")
    duration_minutes = models.PositiveIntegerField(
        default=30,
        help_text="Duration of appointment in minutes"
    )
    appointment_status = models.CharField(
        max_length=20,
        choices=AppointmentStatus.choices,
        default=AppointmentStatus.SCHEDULED,
        help_text="Current status of the appointment"
    )
    paid = models.BooleanField(default=False)
    amount_to_pay = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Internal notes about the appointment"
    )
    feedback = models.TextField(
        blank=True,
        null=True,
        help_text="Patient feedback after appointment"
    )

    def __str__(self):
        return f"{self.clinic_patient.patient.name} - {self.appointment_date} {self.appointment_time}"

    def clean(self):
        super().clean()
        # Validate that doctor belongs to the same clinic as the patient
        if self.doctor and self.clinic_patient:
            if self.doctor.clinic_id != self.clinic_patient.clinic_id:
                raise ValidationError({
                    'doctor': 'Doctor must belong to the same clinic as the patient.'
                })

    class Meta:
        verbose_name = "Appointment"
        verbose_name_plural = "Manage Appointments"
        ordering = ['-appointment_date', '-appointment_time']
        db_table = 'eth_appointment'
