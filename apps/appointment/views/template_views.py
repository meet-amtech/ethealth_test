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
from apps.base.helpers import get_date_str, get_date_obj, get_time_str

logger = logging.getLogger(__name__)


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

            # Build base filters for AppointmentRequest
            filters = {
                'clinic_id': clinic_id
            }

            # Apply date filters
            date_filter = {}
            if start_date:
                try:
                    filters['created_at__date__gte'] = get_date_obj(start_date)
                except:
                    pass
            if end_date:
                try:
                    filters['created_at__date__lte'] = get_date_obj(end_date)
                except:
                    pass

            appointment_requests = AppointmentRequest.objects.filter(
                **filters
            ).select_related(
                'clinic'
            ).prefetch_related(
                'appointments'
            ).order_by('created_at')


            # Apply search filter
            if search_query:
                appointment_requests = appointment_requests.filter(
                    Q(name__icontains=search_query) |
                    Q(phone__icontains=search_query) |
                    Q(request_token__icontains=search_query) |
                    Q(appointment_request_status__icontains=search_query)
                )

            # Prepare data for template
            appointments = []
            for req in appointment_requests:
                # Get related appointment if exists
                appointment = Appointment.objects.filter(
                    appointment_request=req
                ).select_related('clinic_patient__patient').first()

                # Create a dictionary with all required fields for the template
                is_confirmed = req.appointment_request_status == 'confirmed'
                appointment_data = {
                    'id': req.id,
                    'token_number': req.request_token,
                    'appointment_date': getattr(appointment, 'appointment_date', None) if is_confirmed else None,
                    'appointment_time': getattr(appointment, 'appointment_time', None) if is_confirmed else None,
                    'request_created_at': req.created_at,
                    'date_str': get_date_str(getattr(appointment, 'appointment_date', None)) if is_confirmed else req.created_at.strftime('%d/%m/%Y'),
                    'time_str': get_time_str(getattr(appointment, 'appointment_time', None)) if is_confirmed else '-',
                    'clinic_patient': {
                        'patient': {
                            'name': req.name,
                            'age': req.age,
                            'phone_number': req.phone,
                            'user': {'phone_number': req.phone} if req.phone else None
                        }
                    },
                    'amount_to_pay': getattr(appointment, 'amount_to_pay', None),
                    'appointment_status': req.appointment_status if is_confirmed and hasattr(req, 'appointment_status') and req.appointment_status else req.appointment_request_status,
                    'appointment_request': req,
                    'doctor': getattr(appointment, 'doctor', None) if appointment else None
                }
                
                # If there's a related appointment, include its data
                if appointment and appointment.clinic_patient:
                    appointment_data.update({
                        'clinic_patient': {
                            'patient': {
                                'name': appointment.clinic_patient.patient.name,
                                'age': appointment.clinic_patient.patient.age,
                                'phone_number': appointment.clinic_patient.patient.phone_number,
                                'user': {'phone_number': appointment.clinic_patient.patient.phone_number} if appointment.clinic_patient.patient.phone_number else None
                            }
                        },
                        'amount_to_pay': appointment.amount_to_pay,
                        'appointment_status': appointment.appointment_status,
                        'doctor': appointment.doctor
                    })
                
                appointments.append(type('AppointmentObject', (), appointment_data))

            # Combine status choices from both models
            # status_choices = list(AppointmentRequestStatus.choices)
            # status_choices.extend([(f'appt_{status[0]}', status[1]) for status in AppointmentStatus.choices if status[0] not in [s[0] for s in status_choices]])
            
            context = {
                'appointments': appointments,
                # 'status_choices': status_choices,
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
            doctor = ClinicUser.objects.filter(
                clinic_id=clinic_id,
                role=ClinicUserRole.ADMIN
            ).first()

            # Get clinic
            clinic = get_object_or_404(Clinic, id=clinic_id)

            context = {
                'doctor': doctor,
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
            patient_dob_str = request.POST.get('patient_dob', '').strip()
            appointment_datetime_str = request.POST.get('appointment_datetime')
            duration = request.POST.get('duration_minutes', '30')
            amount = request.POST.get('amount_to_pay', '').strip()
            notes = request.POST.get('notes', '').strip()

            # Validate required fields
            if not all([patient_name, appointment_datetime_str]):
                messages.error(request, "Patient name and appointment date & time are required.")
                return redirect('template_appointment:appointment_create')

            # Enforce phone number required
            if not patient_phone:
                messages.error(request, "Patient phone number is required.")
                return redirect('template_appointment:appointment_create')

            # Parse datetime
            try:
                # Format: DD/MM/YYYY hh:mm A (e.g., 11/11/2025 02:30 PM)
                appointment_datetime = datetime.datetime.strptime(
                    appointment_datetime_str, 
                    '%d/%m/%Y %I:%M %p'
                )
                
                # Validate datetime is not in the past
                # Make both datetimes timezone-aware for comparison
                from django.utils import timezone
                current_time = timezone.now()
                appointment_datetime = timezone.make_aware(appointment_datetime)
                
                if appointment_datetime < current_time:
                    messages.error(request, "Appointment date and time cannot be in the past.")
                    return redirect('template_appointment:appointment_create')
                    
                # Split into date and time for the model
                appointment_date = appointment_datetime.date()
                appointment_time = appointment_datetime.time()
                
            except ValueError as e:
                logger.error(f"Error parsing datetime: {str(e)}")
                messages.error(request, "Invalid datetime format. Please use the datetime picker.")
                return redirect('template_appointment:appointment_create')

            # Get or create patient and clinic_patient
            with transaction.atomic():
                # Get clinic
                clinic = get_object_or_404(Clinic, id=clinic_id)
                
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
                appointment =  appointment_request.appointments.first()
                clinic_patient = appointment.clinic_patient
                clinic_patient.created_by =  request.user
                clinic_patient.save()

                patient = clinic_patient.patient
                patient.age = int(patient_age) if patient_age else None
                patient.gender = patient_gender
                if patient_dob_str:
                    patient.date_of_birth = get_date_obj(patient_dob_str)
                patient.created_by = request.user
                patient.save()

                appointment.appointment_date = appointment_datetime.date()
                appointment.appointment_time = appointment_datetime.time()
                appointment.duration_minutes = int(duration) if duration else 0
                appointment.appointment_status = AppointmentStatus.SCHEDULED
                appointment.amount_to_pay = float(amount) if amount else 0.0
                appointment.doctor = appointment_request.clinic.clinic_users.filter(role=ClinicUserRole.ADMIN).first()
                appointment.paid = False
                appointment.notes = notes
                appointment.created_by = request.user
                appointment.save()
                
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

            appointment_request_id = kwargs.get('pk')
            
            # Try to get the appointment request
            appointment_request = get_object_or_404(
                AppointmentRequest,
                id=appointment_request_id,
                clinic_id=clinic_id
            )
            appointment = appointment_request.appointments.first()    
            # Get doctor for this clinic
            doctor = appointment_request.clinic.clinic_users.filter(role=ClinicUserRole.ADMIN).first()

            context = {
                'appointment': appointment,
                'appointment_request': appointment_request,
                'doctor': doctor,
                'status_choices':  AppointmentStatus.choices if appointment_request.appointment_request_status == AppointmentRequestStatus.CONFIRMED else AppointmentRequestStatus.choices,
                'appointmentreqest_status_choices': AppointmentRequestStatus.choices,
                'gender_choices': Gender.choices
            }
            
            if appointment:
                # Existing appointment - format dates and add to context
                appointment.date_str = get_date_str(appointment.appointment_date)
                appointment.time_str = get_time_str(appointment.appointment_time)
                context.update({
                    'phone_number': appointment.clinic_patient.patient.phone_number or '',
                    'token_number': appointment_request.request_token or '',
                })
            else:
                # New appointment - use request details
                context.update({
                    'phone_number': appointment_request.phone or '',
                    'token_number': appointment_request.request_token or '',
                })
            
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

            appointment_request_id = kwargs.get('pk')
            
            # Get the appointment request
            appointment_request = get_object_or_404(
                AppointmentRequest,
                id=appointment_request_id,
                clinic_id=clinic_id
            )

            # Get form data
            patient_name = request.POST.get('patient_name', '').strip()
            patient_age = request.POST.get('patient_age', '').strip()
            patient_phone = request.POST.get('patient_phone', '').strip()
            patient_dob_str = request.POST.get('patient_dob', '').strip()
            patient_gender = request.POST.get('patient_gender', '').strip()
            doctor_id = request.POST.get('doctor_id')
            appointment_datetime_str = request.POST.get('appointment_datetime')
            duration = request.POST.get('duration_minutes')
            status = request.POST.get('appointment_status')
            amount = request.POST.get('amount_to_pay', '0').strip()
            paid = request.POST.get('paid') == 'on'
            notes = request.POST.get('notes', '').strip()
            feedback = request.POST.get('feedback', '').strip()
            
            # Parse combined datetime string
            appointment_datetime = None
            if appointment_datetime_str:
                try:
                    appointment_datetime = datetime.datetime.strptime(
                        appointment_datetime_str, '%d/%m/%Y %I:%M %p'
                    )
                except (ValueError, TypeError) as e:
                    logger.error(f"Error parsing appointment datetime: {str(e)}")
                    messages.error(request, "Invalid appointment date/time format. Please use DD/MM/YYYY HH:MM AM/PM")
                    return redirect('template_appointment:appointment_edit', pk=appointment_request_id)
            else:
                messages.error(request, "Appointment date and time are required.")
                return redirect('template_appointment:appointment_edit', pk=appointment_request_id)

            with transaction.atomic():
                appointment = appointment_request.appointments.first()
                if appointment:
                    # Update existing appointment logic
                    appointment_request.name = patient_name
                    appointment_request.phone = patient_phone
                    appointment_request.age = int(patient_age) if patient_age else None
                    appointment_request.gender = patient_gender
                    appointment_request.updated_by = request.user
                    appointment_request.save()

                    patient = appointment.clinic_patient.patient
                    patient.name = patient_name
                    patient.age = int(patient_age) if patient_age else None
                    patient.phone_number = patient_phone
                    if patient_dob_str:
                        try:
                            patient.date_of_birth = get_date_obj(patient_dob_str)
                        except (ValueError, TypeError):
                            messages.warning(request, "Invalid date of birth format. DOB not updated.")
                    patient.updated_by = request.user
                    patient.save()
                    
                    appointment.appointment_date = appointment_datetime.date()
                    appointment.appointment_time = appointment_datetime.time()
                    appointment.duration_minutes = int(duration) if duration else 30
                    appointment.appointment_status = status
                    appointment.amount_to_pay = float(amount) if amount else 0.0
                    appointment.paid = paid
                    if status == AppointmentStatus.SCHEDULED:
                        appointment.status = AppointmentStatus.SCHEDULED
                    elif status == AppointmentStatus.IN_PROGRESS:
                        appointment.status = AppointmentStatus.IN_PROGRESS
                    elif status == AppointmentStatus.COMPLETED:
                        appointment.status = AppointmentStatus.COMPLETED
                    elif status == AppointmentStatus.CANCELLED:
                        appointment.status = AppointmentStatus.CANCELLED
                    appointment.notes = notes
                    appointment.feedback = feedback
                    appointment.updated_by = request.user
                    appointment.save()
                    
                    messages.success(request, "Appointment updated successfully.")
                else:
                    # Create new appointment logic
                    appointment_request.name = patient_name
                    appointment_request.phone = patient_phone
                    appointment_request.age = int(patient_age) if patient_age else None
                    appointment_request.gender = patient_gender
                    appointment_request.updated_by = request.user

                    if status == AppointmentRequestStatus.CANCELLED:
                        appointment_request.appointment_request_status = AppointmentRequestStatus.CANCELLED
                        appointment_request.confirmed_at = timezone.now()
                        appointment_request.save()
                        messages.info(request, "Appointment request was cancelled.")
                        
                    elif status == AppointmentRequestStatus.PENDING:
                        appointment_request.appointment_request_status = AppointmentRequestStatus.PENDING
                        appointment_request.confirmed_at = timezone.now()
                        appointment_request.save()
                        messages.info(request, "Appointment request was pending.")

                    if status == AppointmentRequestStatus.CONFIRMED:
                        appointment_request.appointment_request_status = AppointmentRequestStatus.CONFIRMED
                        appointment_request.confirmed_at = timezone.now()
                        appointment_request.save()
                        
                        appointment =  appointment_request.appointments.first()
                        clinic_patient = appointment.clinic_patient
                        clinic_patient.created_by =  request.user
                        clinic_patient.save()

                        patient = clinic_patient.patient
                        patient.age = int(patient_age) if patient_age else None
                        patient.gender = patient_gender
                        if patient_dob_str:
                            patient.date_of_birth = get_date_obj(patient_dob_str)
                        patient.created_by = request.user
                        patient.save()
                        
                        appointment.appointment_date = appointment_datetime.date()
                        appointment.appointment_time = appointment_datetime.time()
                        appointment.duration_minutes = int(duration) if duration else 30
                        appointment.appointment_status = AppointmentStatus.SCHEDULED
                        appointment.amount_to_pay = float(amount) if amount else 0.0
                        appointment.doctor = appointment_request.clinic.clinic_users.filter(Q(role=ClinicUserRole.DOCTOR) | Q(role=ClinicUserRole.ADMIN)& Q(is_active=True)).first()
                        appointment.paid = paid
                        appointment.notes = notes
                        appointment.feedback = feedback
                        appointment.created_by = request.user
                        appointment.save()
                        messages.success(request, "Appointment created successfully.")
                    

            messages.success(request, "Appointment updated successfully.")
            return redirect(self.success_url)

        except Exception as e:
            logger.error(f"Error updating appointment: {str(e)}", exc_info=True)
            messages.error(request, f"Error updating appointment: {str(e)}")
            return redirect(reverse_lazy('template_appointment:appointment_update', kwargs={'pk': appointment_request_id}))


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

            appointment_request_id = kwargs.get('pk')
            appointment_request = get_object_or_404(
                AppointmentRequest,
                id=appointment_request_id,
                clinic_id=clinic_id,
                is_deleted=False
            )

            # Soft delete the appointment request and the appointment if it exists
            with transaction.atomic():
                appointment_request.is_deleted = True
                appointment_request.is_active = False
                appointment_request.updated_by = request.user
                appointment_request.save()

                appointment = appointment_request.appointments.first()
                if appointment:
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
