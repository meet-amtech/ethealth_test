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

            # Build base filters for AppointmentRequest
            filters = {
                'clinic_id': clinic_id,
                'is_deleted': False,
                'is_active': True
            }

            # Apply date filters
            date_filter = {}
            if start_date:
                try:
                    date_filter['appointment_date__gte'] = get_date_obj(start_date)
                except:
                    pass
            if end_date:
                try:
                    date_filter['appointment_date__lte'] = get_date_obj(end_date)
                except:
                    pass

            # Get appointment requests with related data
            from django.db.models import Prefetch, OuterRef, Subquery
            
            # Subquery to get related appointment status if exists
            appointment_status_subquery = Appointment.objects.filter(
                appointment_request_id=OuterRef('pk')
            ).values('appointment_status')[:1]

            appointment_requests = AppointmentRequest.objects.filter(
                **filters
            ).annotate(
                appointment_status=Subquery(appointment_status_subquery)
            ).select_related(
                'clinic'
            ).order_by('-created_at')

            # Apply search filter
            if search_query:
                appointment_requests = appointment_requests.filter(
                    Q(name__icontains=search_query) |
                    Q(phone__icontains(search_query)) |
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
                appointment_data = {
                    'id': req.id,
                    'token_number': req.request_token,
                    'appointment_date': getattr(appointment, 'appointment_date', None),
                    'date_str': get_date_str(getattr(appointment, 'appointment_date', None)) if getattr(appointment, 'appointment_date', None) else '-',
                    'appointment_time': getattr(appointment, 'appointment_time', None),
                    'time_str': get_time_str(getattr(appointment, 'appointment_time', None)) if getattr(appointment, 'appointment_time', None) else '-',
                    'clinic_patient': {
                        'patient': {
                            'name': req.name,
                            'age': req.age,
                            'phone_number': req.phone,
                            'user': {'phone_number': req.phone} if req.phone else None
                        }
                    },
                    'amount_to_pay': getattr(appointment, 'amount_to_pay', None),
                    'appointment_status': req.appointment_status if req.appointment_request_status == 'confirmed' and hasattr(req, 'appointment_status') and req.appointment_status else req.appointment_request_status,
                    'appointment_request': req,
                    'is_confirmed': req.appointment_request_status == 'confirmed',
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
            status_choices = list(AppointmentRequestStatus.choices)
            status_choices.extend([(f'appt_{status[0]}', status[1]) for status in AppointmentStatus.choices if status[0] not in [s[0] for s in status_choices]])
            
            context = {
                'appointments': appointments,
                'status_choices': status_choices,
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
                role__in=[ClinicUserRole.DOCTOR, ClinicUserRole.ADMIN],
                is_active=True,
                is_deleted=False
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
            doctor_id = request.POST.get('doctor_id')
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
                clinic = get_object_or_404(Clinic, id=clinic_id, is_deleted=False)

                # Parse patient date of birth if provided
                patient_dob = None
                if patient_dob_str:
                    try:
                        patient_dob = get_date_obj(patient_dob_str)
                    except Exception:
                        messages.warning(request, "Invalid date of birth format. Use DD/MM/YYYY. Skipping DOB.")

                # Handle User creation/linking if phone number is provided
                user_obj = None
                if patient_phone:
                    # Get or create User with phone number
                    user_obj, user_created = User.objects.get_or_create(
                        phone_number=patient_phone,
                        defaults={'is_active': True}
                    )

                # Get or create patient (prefer by phone if provided)
                patient = None
                if patient_phone:
                    patient = Patient.objects.filter(phone_number=patient_phone, is_deleted=False).first()
                if not patient:
                    patient, created = Patient.objects.get_or_create(
                        name=patient_name,
                        defaults={
                            'age': int(patient_age) if patient_age else None,
                            'date_of_birth': patient_dob if patient_dob else None,
                            'phone_number': patient_phone,
                            'created_by': request.user,
                            'updated_by': request.user
                        }
                    )
                else:
                    created = False

                # Update patient fields if provided and patient already exists
                if not created:
                    changed = False
                    if patient_age:
                        patient.age = int(patient_age)
                        changed = True
                    if patient_dob:
                        patient.date_of_birth = patient_dob
                        changed = True
                    if patient_phone and patient.phone_number != patient_phone:
                        patient.phone_number = patient_phone
                        changed = True
                    if changed:
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
            
            # Get phone number from patient
            phone_number = appointment.clinic_patient.patient.phone_number or ''
            
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
            patient_dob_str = request.POST.get('patient_dob', '').strip()
            doctor_id = request.POST.get('doctor_id')
            appointment_datetime_str = request.POST.get('appointment_datetime')
            duration = request.POST.get('duration_minutes')
            status = request.POST.get('appointment_status')
            amount = request.POST.get('amount_to_pay', '').strip()
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
                    return redirect('template_appointment:appointment_edit', pk=appointment_id)

            # Update appointment datetime if provided
            if appointment_datetime:
                appointment.appointment_date = appointment_datetime.date()
                appointment.appointment_time = appointment_datetime.time()

            # Update appointment
            with transaction.atomic():
                # Handle phone number update
                if patient_phone:
                    # Get or create User with new phone number
                    user_obj, user_created = User.objects.get_or_create(
                        phone_number=patient_phone,
                        defaults={'is_active': True}
                    )
                    # Update patient's user link and phone
                    appointment.clinic_patient.patient.user = user_obj
                    appointment.clinic_patient.patient.phone_number = patient_phone
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

                # Update patient date of birth
                if patient_dob_str:
                    try:
                        new_dob = get_date_obj(patient_dob_str)
                        appointment.clinic_patient.patient.date_of_birth = new_dob
                        appointment.clinic_patient.patient.updated_by = request.user
                        appointment.clinic_patient.patient.save()
                    except Exception:
                        messages.warning(request, "Invalid date of birth format. Use DD/MM/YYYY. DOB not updated.")

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

                # Date and time are already updated from the combined datetime field at the start of the method
                # No need to parse them again here

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
                if appointment.appointment_status == AppointmentStatus.IN_PROGRESS and appointment.appointment_request.request_token:
                    appointment.clinic_patient.clinic.current_token_number = appointment.appointment_request.request_token
                    appointment.clinic_patient.clinic.save()
                #     appointment.clinic_patient__clinic.save()

                # Auto-update status based on payment
                # if paid and appointment.amount_to_pay and float(appointment.amount_to_pay) > 0:
                #     if appointment.appointment_status == AppointmentStatus.SCHEDULED:
                #         appointment.appointment_status = AppointmentStatus.IN_PROGRESS

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
