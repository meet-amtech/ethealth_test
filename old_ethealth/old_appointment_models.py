import datetime
import logging

from django.core.exceptions import ValidationError
from django.db import models
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
from django.db import transaction

from apps.base.models import Base
from apps.clinic.models import Clinic
from apps.doctor.models import Doctor
from apps.patient.models import Patient, ClinicPatient
from apps.users.models import User

logger = logging.getLogger(__name__)


class APPOINTMENT_REQUEST_STATUS(models.TextChoices):
    REQUESTED = 'requested', _('Requested')
    COMPLETED = 'completed', _('Completed')


class AppointmentRequest(Base):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=10, validators=[RegexValidator(
        regex=r"^\d{10}", message="Phone number must be 10 digits only.")])
    date = models.DateField()
    start_time = models.TimeField(null=True)
    end_time = models.TimeField(null=True)
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name='appointment_requests')
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, related_name='appointment_requests', null=True)
    request_token = models.PositiveIntegerField()
    reschedule_attempts = models.PositiveIntegerField(default=0)
    appointment_request_status = models.CharField(
        max_length=15,
        choices=APPOINTMENT_REQUEST_STATUS.choices,
        default='requested',
        help_text="Indicates the status of the appointment request action."
    )
    height = models.FloatField(null=True, blank=True, help_text=_("Height in feet."))
    weight = models.FloatField(null=True, blank=True, help_text=_("Weight in kilograms."))

    def __str__(self):
        return f"{self.name} - {self.phone} - {self.doctor} - {self.clinic.name} - {self.date} - {self.start_time} to {self.end_time}"

    def clean(self):
        # if self.start_time and self.end_time:
        #     validate_time(self.date, self.start_time, self.end_time, datetime.date.today(), datetime.datetime.now().time())
        self.start_time = datetime.datetime.now().time()
        self.end_time = (datetime.datetime.now() + datetime.timedelta(minutes=30)).time()
        if self.doctor and self.clinic:
            if self.clinic not in self.doctor.clinics.all():
                raise ValidationError("Doctor does not belong to the selected clinic.")

    def save(self, *args, **kwargs):
        if self.appointment_request_status == 'completed':
            # Use atomic transaction to ensure data integrity
            with transaction.atomic():
                patient_user = User.create_user(name=self.name, phone=self.phone, role='patient')
                if not patient_user:
                    logger.error("Failed to create a user for the patient.")
                    raise ValidationError("Failed to create a user for the patient.")
                patient = Patient.create_patient(user=patient_user)
                if not patient:
                    logger.error("Failed to create a patient.")
                    raise ValidationError("Failed to create a patient.")
                clinic_patient = ClinicPatient.create_clinic_patient(patient=patient, clinic=self.clinic)
                if not clinic_patient:
                    logger.error("Failed to create a clinic patient.")
                    raise ValidationError("Failed to create a clinic patient.")
                Appointment.objects.get_or_create(patient=patient, appointment_request=self, phone=self.phone, address=self.clinic.address)
        super().save(*args, **kwargs)

    def generate_next_request_token(self):
        if not self.clinic.is_active:
            logger.error("The clinic is closed.")
            raise ValueError("The clinic is closed.")

        if self.clinic and self.clinic.reset_token:
            self.clinic.reset_token = False
            self.clinic.save()
            return 1

        last_request_token = AppointmentRequest.objects.filter(clinic_id=self.clinic_id).order_by('-date', '-created_at').first()
        if last_request_token and (datetime.datetime.today().date() > last_request_token.date):
            return 1

        elif last_request_token:
            return last_request_token.request_token + 1

        return 1

    class Meta:
        verbose_name = "Appointment Request"
        verbose_name_plural = "Manage Appointment Requests"
        ordering = ['-created_at']
        db_table = "eth_appointment_request"


class AppointmentRescheduleHistory(Base):
    appointment_request = models.ForeignKey(
        AppointmentRequest,
        on_delete=models.CASCADE, related_name='reschedule_histories'
    )
    date = models.DateField(help_text="The previous date of the appointment before it was rescheduled.")
    start_time = models.TimeField(
        help_text="The previous start time of the appointment before it was rescheduled.")
    end_time = models.TimeField(
        help_text="The previous end time of the appointment before it was rescheduled."
    )
    doctor = models.ForeignKey(
        Doctor, on_delete=models.SET_NULL, null=True, related_name='reschedule_histories',
        help_text="The previous doctor of the appointment before it was rescheduled."
    )
    reason_for_rescheduling = models.TextField(
        blank=True, null=True,
        help_text="Reason for the appointment reschedule."
    )
    reschedule_status = models.CharField(
        max_length=10,
        choices=[('pending', 'Pending'), ('confirmed', 'Confirmed')],
        default='pending',
        help_text="Indicates the status of the reschedule action."
    )

    def __str__(self):
        return f"Reschedule history for {self.appointment_request} from {self.date}"

    def clean(self):
        if self.date and self.start_time and self.end_time:
            self.validate_time(self.date, self.start_time, self.end_time, datetime.date.today(), datetime.datetime.now().time())
            self.validate_time(self.date, self.start_time, self.end_time, self.appointment_request.date, self.appointment_request.start_time, True)

    class Meta:
        verbose_name = "Appointment Reschedule History"
        verbose_name_plural = "Manage Appointment Reschedule Histories"
        ordering = ['-created_at']
        db_table = "eth_appointment_reschedule_history"


class Appointment(Base):
    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, related_name='appointments', null=True)
    appointment_request = models.OneToOneField(AppointmentRequest, on_delete=models.CASCADE)
    phone = models.CharField(max_length=10, validators=[RegexValidator(
        regex=r"^\d{10}", message="Phone number must be 10 digits only.")])
    address = models.CharField(max_length=255, blank=True, null=True, default="",
                               help_text="Does not have to be specific, just the city and the state")
    want_reminder = models.BooleanField(default=False)
    additional_info = models.TextField(blank=True, null=True)
    paid = models.BooleanField(default=False)
    amount_to_pay = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    appointment_status = models.CharField(
        max_length=20,
        choices=[('attended', 'Attended'), ('payment_pending', 'Payment Pending'), ('paid', 'Paid')],
        default='requested',
        help_text="Indicates the status of the appointment action."
    )
    comment = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.patient} - {self.appointment_request.doctor} - {self.appointment_request.clinic}" \
               f"{self.appointment_request.start_time.strftime('%Y-%m-%d %H:%M')} to " \
               f"{self.appointment_request.end_time.strftime('%Y-%m-%d %H:%M')}"

    # def clean(self):
    #     if self.appointment_request.start_time and self.appointment_request.end_time:
    #         validate_time(self.appointment_request.date, self.appointment_request.start_time, self.appointment_request.end_time, datetime.date.today(), datetime.datetime.now().time())

    class Meta:
        verbose_name = "Appointment"
        verbose_name_plural = "Manage Appointments"
        ordering = ['-created_at']
        db_table = "eth_appointment"
