import datetime
import logging
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.urls import reverse_lazy
from django.db.models import Q
from django.contrib import messages
from django.db import transaction
from django.utils import timezone

from apps.appointment.models import (
    AppointmentRequest, 
    Appointment, 
    Patient, 
    ClinicPatient,
    AppointmentRequestStatus,
    AppointmentStatus
)
from apps.clinic.models import Clinic, ClinicUser, ClinicUserRole, Gender
from apps.users.models import User
from apps.base.helpers import get_today_date_obj, get_date_str, get_date_obj, get_time_str, get_time_obj

logger = logging.getLogger(__name__)


class AppointmentRequestListView(LoginRequiredMixin, View):
    """View for listing all appointment requests"""
    template_name = "appointment/appointment-requests.html"
    login_url = reverse_lazy('template_user:login')

    def get(self, request, *args, **kwargs):
        try:
            clinic_id = request.session.get('clinic_id')
            if not clinic_id:
                messages.error(request, "No clinic selected.")
                return redirect('dashboard')

            # Get date filters from request
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            status_filter = request.GET.get('status', '')

            # Build filters
            filters = {
                'clinic_id': clinic_id,
                'is_deleted': False,
                'is_active': True
            }

            # Apply date filters
            if start_date:
                try:
                    filters['created_at__gte'] = get_date_obj(start_date)
                except:
                    pass
            if end_date:
                try:
                    filters['created_at__lte'] = get_date_obj(end_date)
                except:
                    pass

            # Apply status filter
            if status_filter:
                filters['appointment_request_status'] = status_filter

            # Get appointment requests
            appointment_requests = AppointmentRequest.objects.filter(
                **filters
            ).select_related('clinic').order_by('-created_at')

            # Format dates for display
            for req in appointment_requests:
                req.created_at_str = get_date_str(req.created_at.date()) if req.created_at else ''
                req.confirmed_at_str = get_date_str(req.confirmed_at.date()) if req.confirmed_at else ''

            context = {
                'appointment_requests': appointment_requests,
                'status_choices': AppointmentRequestStatus.choices,
                'current_status': status_filter,
            }
            return render(request, self.template_name, context)

        except Exception as e:
            logger.error(f"Error loading appointment requests: {str(e)}", exc_info=True)
            messages.error(request, "Failed to load appointment requests.")
            return redirect('dashboard')


class AppointmentListView(LoginRequiredMixin, View):
    """View for listing all confirmed appointments"""
    template_name = "appointment/appointments.html"
    login_url = reverse_lazy('template_user:login')

    def get(self, request, *args, **kwargs):
        try:
            clinic_id = request.session.get('clinic_id')
            if not clinic_id:
                messages.error(request, "No clinic selected.")
                return redirect('dashboard')

            # Get filters
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            status_filter = request.GET.get('status', '')
            search_query = request.GET.get('search', '').strip()

            # Build filters
            filters = {
                'clinic_patient__clinic_id': clinic_id,
                'is_deleted': False,
                'is_active': True
            }

            # Apply date filters
            if start_date:
                try:
                    filters['appointment_date__gte'] = get_date_obj(start_date)
                except:
                    pass
            else:
                # Default to today's appointments
                filters['appointment_date__gte'] = get_today_date_obj().date()

            if end_date:
                try:
                    filters['appointment_date__lte'] = get_date_obj(end_date)
                except:
                    pass
            else:
                # Default to today's appointments
                filters['appointment_date__lte'] = get_today_date_obj().date()

            # Apply status filter
            if status_filter:
                filters['appointment_status'] = status_filter

            # Get appointments
            appointments = Appointment.objects.filter(
                **filters
            ).select_related(
                'clinic_patient__patient__user',
                'clinic_patient__clinic',
                'doctor',
                'appointment_request'
            ).order_by('-appointment_date', '-appointment_time')

            # Apply search filter on all displayed fields
            if search_query:
                appointments = appointments.filter(
                    Q(clinic_patient__patient__name__icontains=search_query) |
                    Q(clinic_patient__patient__user__phone_number__icontains=search_query) |
                    Q(doctor__name__icontains=search_query) |
                    Q(appointment_request__request_token__icontains=search_query) |
                    Q(appointment_status__icontains=search_query)
                )

            # Format dates and times for display
            for appointment in appointments:
                appointment.date_str = get_date_str(appointment.appointment_date)
                appointment.time_str = get_time_str(appointment.appointment_time)
                # Get phone number from patient's user
                if appointment.clinic_patient.patient.user:
                    appointment.phone_number = appointment.clinic_patient.patient.user.phone_number
                else:
                    appointment.phone_number = None
                # Get token number from appointment request
                if appointment.appointment_request:
                    appointment.token_number = appointment.appointment_request.request_token
                else:
                    appointment.token_number = None

            context = {
                'appointments': appointments,
                'status_choices': AppointmentStatus.choices,
                'current_status': status_filter,
                'search_query': search_query,
            }
            return render(request, self.template_name, context)

        except Exception as e:
            logger.error(f"Error loading appointments: {str(e)}", exc_info=True)
            messages.error(request, "Failed to load appointments.")
            return redirect('dashboard')



class AppointmentCreateView(LoginRequiredMixin, View):
    """View for creating appointments directly from dashboard"""
    template_name = "appointment/add-appointment.html"
    login_url = reverse_lazy('template_user:login')
    success_url = reverse_lazy('template_appointment:appointment_list')

    def get(self, request, *args, **kwargs):
        try:
            clinic_id = request.session.get('clinic_id')
            if not clinic_id:
                messages.error(request, "No clinic selected.")
                return redirect('dashboard')

            # Get doctors for this clinic
            doctors = ClinicUser.objects.filter(
                clinic_id=clinic_id,
                role__in=[ClinicUserRole.DOCTOR, ClinicUserRole.ADMIN],
                is_active=True,
                is_deleted=False
            )

            # Get clinic
            clinic = get_object_or_404(Clinic, id=clinic_id)

            context = {
                'doctors': doctors,
                'clinic': clinic,
                'gender_choices': Gender.choices,
            }
            return render(request, self.template_name, context)

        except Exception as e:
            logger.error(f"Error loading appointment form: {str(e)}", exc_info=True)
            messages.error(request, "Failed to load form.")
            return redirect(self.success_url)

    def post(self, request, *args, **kwargs):
        try:
            clinic_id = request.session.get('clinic_id')
            if not clinic_id:
                messages.error(request, "No clinic selected.")
                return redirect('dashboard')

            # Get form data
            patient_name = request.POST.get('patient_name', '').strip()
            patient_age = request.POST.get('patient_age', '').strip()
            patient_gender = request.POST.get('patient_gender', '')
            patient_phone = request.POST.get('patient_phone', '')
            doctor_id = request.POST.get('doctor_id')
            appointment_date_str = request.POST.get('appointment_date')
            appointment_time_str = request.POST.get('appointment_time')
            duration = request.POST.get('duration_minutes', '30')
            amount = request.POST.get('amount_to_pay', '').strip()
            notes = request.POST.get('notes', '').strip()

            # Validate required fields
            if not all([patient_name, appointment_date_str, appointment_time_str]):
                messages.error(request, "Patient name, date, and time are required.")
                return redirect('template_appointment:appointment_create')

            # Parse date and time
            try:
                appointment_date = get_date_obj(appointment_date_str)
                appointment_time = get_time_obj(appointment_time_str)
            except Exception as e:
                logger.error(f"Error parsing date/time: {str(e)}")
                messages.error(request, "Invalid date or time format. Use DD/MM/YYYY for date and HH:MM AM/PM for time.")
                return redirect('template_appointment:appointment_create')

            # Validate date is not in the past
            if appointment_date < get_today_date_obj().date():
                messages.error(request, "Appointment date cannot be in the past.")
                return redirect('template_appointment:appointment_create')

            # Get or create patient and clinic_patient
            with transaction.atomic():
                # Get clinic
                clinic = get_object_or_404(Clinic, id=clinic_id, is_deleted=False)

                # Handle User creation/linking if phone number is provided
                user_obj = None
                if patient_phone:
                    # Get or create User with phone number
                    user_obj, user_created = User.objects.get_or_create(
                        phone_number=patient_phone,
                        defaults={'is_active': True}
                    )

                # Get or create patient
                patient = None
                if user_obj:
                    # Try to find existing patient linked to this user
                    patient = Patient.objects.filter(user=user_obj, is_deleted=False).first()
                
                if not patient:
                    # Create new patient or find by name if no user
                    patient = Patient.objects.create(
                        user=user_obj,
                        name=patient_name,
                        age=int(patient_age) if patient_age else None,
                        created_by=request.user,
                        updated_by=request.user
                    )
                else:
                    # Update existing patient details
                    patient.name = patient_name
                    if patient_age:
                        patient.age = int(patient_age)
                    patient.updated_by = request.user
                    patient.save()

                # Get or create clinic_patient
                clinic_patient, created = ClinicPatient.objects.get_or_create(
                    clinic=clinic,
                    patient=patient,
                    defaults={
                        'created_by': request.user,
                        'updated_by': request.user
                    }
                )

                # Get doctor if provided
                doctor = None
                if doctor_id:
                    doctor = ClinicUser.objects.filter(
                        id=doctor_id,
                        clinic_id=clinic_id,
                        role__in=[ClinicUserRole.DOCTOR, ClinicUserRole.ADMIN],
                        is_deleted=False
                    ).first()

                # Create appointment request for tracking
                appointment_request = None
                if patient_phone:
                    appointment_request = AppointmentRequest.objects.create(
                        name=patient_name,
                        phone=patient_phone,
                        age=int(patient_age) if patient_age else None,
                        gender=patient_gender if patient_gender else None,
                        clinic=clinic,
                        appointment_request_status=AppointmentRequestStatus.CONFIRMED,
                        confirmed_at=timezone.now(),
                        expired_at=timezone.now() + timedelta(days=1),
                        created_by=request.user,
                        updated_by=request.user
                    )
                
                # Create appointment
                appointment = Appointment.objects.create(
                    clinic_patient=clinic_patient,
                    doctor=doctor,
                    appointment_date=appointment_date,
                    appointment_time=appointment_time,
                    duration_minutes=int(duration) if duration else 30,
                    amount_to_pay=float(amount) if amount else None,
                    notes=notes,
                    appointment_status=AppointmentStatus.SCHEDULED,
                    created_by=request.user,
                    updated_by=request.user,
                    appointment_request=appointment_request
                )

            messages.success(request, f"Appointment created successfully for {patient_name} on {get_date_str(appointment_date)} at {get_time_str(appointment_time)}.")
            return redirect(self.success_url)

        except Exception as e:
            logger.error(f"Error creating appointment: {str(e)}", exc_info=True)
            messages.error(request, f"Error creating appointment: {str(e)}")
            return redirect('template_appointment:appointment_create')


class AppointmentUpdateView(LoginRequiredMixin, View):
    """View for updating existing appointments"""
    template_name = "appointment/edit-appointment.html"
    login_url = reverse_lazy('template_user:login')
    success_url = reverse_lazy('template_appointment:appointment_list')

    def get(self, request, *args, **kwargs):
        try:
            clinic_id = request.session.get('clinic_id')
            if not clinic_id:
                messages.error(request, "No clinic selected.")
                return redirect('dashboard')

            appointment_id = kwargs.get('pk')
            appointment = get_object_or_404(
                Appointment,
                id=appointment_id,
                clinic_patient__clinic_id=clinic_id,
                is_deleted=False
            )

            # Get doctors for this clinic
            doctors = ClinicUser.objects.filter(
                clinic_id=clinic_id,
                role__in=[ClinicUserRole.DOCTOR, ClinicUserRole.ADMIN],
                is_active=True,
                is_deleted=False
            )

            # Format dates for display
            appointment.date_str = get_date_str(appointment.appointment_date)
            appointment.time_str = get_time_str(appointment.appointment_time)
            
            # Get phone number from patient's user
            phone_number = ''
            if appointment.clinic_patient.patient.user:
                phone_number = appointment.clinic_patient.patient.user.phone_number
            
            # Get token number from appointment request
            token_number = ''
            if appointment.appointment_request:
                token_number = appointment.appointment_request.request_token

            context = {
                'appointment': appointment,
                'doctors': doctors,
                'status_choices': AppointmentStatus.choices,
                'gender_choices': Gender.choices,
                'phone_number': phone_number,
                'token_number': token_number,
            }
            return render(request, self.template_name, context)

        except Exception as e:
            logger.error(f"Error loading appointment: {str(e)}", exc_info=True)
            messages.error(request, "Failed to load appointment.")
            return redirect(self.success_url)

    def post(self, request, *args, **kwargs):
        try:
            clinic_id = request.session.get('clinic_id')
            if not clinic_id:
                messages.error(request, "No clinic selected.")
                return redirect('dashboard')

            appointment_id = kwargs.get('pk')
            appointment = get_object_or_404(
                Appointment,
                id=appointment_id,
                clinic_patient__clinic_id=clinic_id,
                is_deleted=False
            )

            # Get form data
            patient_name = request.POST.get('patient_name', '').strip()
            patient_age = request.POST.get('patient_age', '').strip()
            patient_phone = request.POST.get('patient_phone', '').strip()
            doctor_id = request.POST.get('doctor_id')
            appointment_date_str = request.POST.get('appointment_date')
            appointment_time_str = request.POST.get('appointment_time')
            duration = request.POST.get('duration_minutes')
            status = request.POST.get('appointment_status')
            amount = request.POST.get('amount_to_pay', '').strip()
            paid = request.POST.get('paid') == 'on'
            notes = request.POST.get('notes', '').strip()
            feedback = request.POST.get('feedback', '').strip()

            # Update appointment
            with transaction.atomic():
                # Handle phone number update
                if patient_phone:
                    # Get or create User with new phone number
                    user_obj, user_created = User.objects.get_or_create(
                        phone_number=patient_phone,
                        defaults={'is_active': True}
                    )
                    # Update patient's user link
                    appointment.clinic_patient.patient.user = user_obj
                    appointment.clinic_patient.patient.updated_by = request.user
                    appointment.clinic_patient.patient.save()
                
                # Update patient information if provided
                if patient_name and patient_name != appointment.clinic_patient.patient.name:
                    appointment.clinic_patient.patient.name = patient_name
                    appointment.clinic_patient.patient.updated_by = request.user
                    appointment.clinic_patient.patient.save()

                if patient_age:
                    appointment.clinic_patient.patient.age = int(patient_age)
                    appointment.clinic_patient.patient.updated_by = request.user
                    appointment.clinic_patient.patient.save()

                # Update doctor
                if doctor_id:
                    doctor = ClinicUser.objects.filter(
                        id=doctor_id,
                        clinic_id=clinic_id,
                        role__in=[ClinicUserRole.DOCTOR, ClinicUserRole.ADMIN],
                        is_deleted=False
                    ).first()
                    if doctor:
                        appointment.doctor = doctor

                # Update date and time
                if appointment_date_str:
                    try:
                        new_date = get_date_obj(appointment_date_str)
                        if new_date >= get_today_date_obj().date():
                            appointment.appointment_date = new_date
                        else:
                            messages.warning(request, "Appointment date cannot be in the past. Date not updated.")
                    except Exception as e:
                        logger.error(f"Error parsing date: {str(e)}")
                        messages.warning(request, "Invalid date format. Date not updated.")

                if appointment_time_str:
                    try:
                        appointment.appointment_time = get_time_obj(appointment_time_str)
                    except Exception as e:
                        logger.error(f"Error parsing time: {str(e)}")
                        messages.warning(request, "Invalid time format. Time not updated.")

                # Update duration
                if duration:
                    appointment.duration_minutes = int(duration)

                # Update status
                if status:
                    appointment.appointment_status = status

                # Update payment information
                if amount:
                    appointment.amount_to_pay = float(amount)

                appointment.paid = paid

                # Auto-update status based on payment
                if paid and appointment.amount_to_pay and float(appointment.amount_to_pay) > 0:
                    if appointment.appointment_status == AppointmentStatus.SCHEDULED:
                        appointment.appointment_status = AppointmentStatus.IN_PROGRESS

                # Update notes and feedback
                appointment.notes = notes
                appointment.feedback = feedback
                appointment.updated_by = request.user
                appointment.save()

            messages.success(request, "Appointment updated successfully.")
            return redirect(self.success_url)

        except Exception as e:
            logger.error(f"Error updating appointment: {str(e)}", exc_info=True)
            messages.error(request, f"Error updating appointment: {str(e)}")
            return redirect(reverse_lazy('template_appointment:appointment_update', kwargs={'pk': appointment_id}))


class AppointmentDeleteView(LoginRequiredMixin, View):
    """View for deleting appointments (soft delete)"""
    login_url = reverse_lazy('template_user:login')
    success_url = reverse_lazy('template_appointment:appointment_list')

    def post(self, request, *args, **kwargs):
        try:
            clinic_id = request.session.get('clinic_id')
            if not clinic_id:
                messages.error(request, "No clinic selected.")
                return redirect('dashboard')

            appointment_id = kwargs.get('pk')
            appointment = get_object_or_404(
                Appointment,
                id=appointment_id,
                clinic_patient__clinic_id=clinic_id,
                is_deleted=False
            )

            # Soft delete the appointment
            with transaction.atomic():
                appointment.is_deleted = True
                appointment.is_active = False
                appointment.updated_by = request.user
                appointment.save()

            messages.success(request, "Appointment deleted successfully.")
            return redirect(self.success_url)

        except Exception as e:
            logger.error(f"Error deleting appointment: {str(e)}", exc_info=True)
            messages.error(request, "Failed to delete appointment.")
            return redirect(self.success_url)
