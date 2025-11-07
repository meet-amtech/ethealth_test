import datetime
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.db.models import Q
from django.contrib import messages
from django.db import transaction

from apps.base.views import BaseETHView
from apps.appointment.models import AppointmentRequest, Appointment
from apps.clinic.models import Clinic, ClinicDoctor
from apps.doctor.models import Doctor
from apps.base.helpers import get_today_date_obj, get_now_time_obj, get_date_str, get_date_obj, get_time_str, get_time_obj

logger = logging.getLogger(__name__)


class AppointmentListView(BaseETHView):
    template_name = "appointment/appointments.html"

    def get(self, request, *args, **kwargs):
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        filters = {}
        if not start_date:
            start_date = get_today_date_obj()
        else:
            start_date = get_date_obj(start_date)
        if not end_date:
            end_date = get_today_date_obj()
        else:
            end_date = get_date_obj(end_date)
        filters['date__gte'] = start_date
        filters['date__lte'] = end_date

        admin_clinics = ClinicDoctor.get_admin_clinics(request.user.doctors.id).values_list('clinic', flat=True)

        appointment_requests = AppointmentRequest.objects.filter(
            Q(clinic__in=admin_clinics) | Q(doctor__user=request.user),
            is_deleted=False,
            is_active=True,
            **filters,
        )

        for appointment_request in appointment_requests:
            appointment_request.start_time_str = get_time_str(appointment_request.start_time)
            appointment_request.end_time_str = get_time_str(appointment_request.end_time)
            appointment_request.date_str = get_date_str(appointment_request.date)
            if Appointment.objects.filter(appointment_request=appointment_request).exists():
                appointment = Appointment.objects.get(appointment_request=appointment_request)
                appointment_request.appointment = appointment
                if appointment.patient.user.date_of_birth:
                    appointment_request.age = get_today_date_obj().year - appointment.patient.user.date_of_birth.year

        context = {
            "appointment_requests": appointment_requests,
        }
        return render(request, self.template_name, context=context)


class AppointmentUpdateView(BaseETHView):
    template_name = "appointment/edit-appointment.html"
    success_url = reverse_lazy("template_appointment:appointments_list")

    def get(self, request, *args, **kwargs):
        appointment_request_id = kwargs.get('pk')
        appointment_request = get_object_or_404(
            AppointmentRequest, 
            id=appointment_request_id,
            is_deleted=False,
            is_active=True
        )

        # Check if user has permission to edit this appointment
        admin_clinics = ClinicDoctor.get_admin_clinics(request.user.doctors.id).values_list('clinic', flat=True)

        if not (appointment_request.clinic in admin_clinics or appointment_request.doctor.user == request.user):
            logger.error("You don't have permission to edit this appointment.")
            messages.error(request=request, message="You don't have permission to edit this appointment.")
            return redirect(self.success_url)

        if Appointment.objects.filter(appointment_request=appointment_request).exists():
            appointment = Appointment.objects.get(appointment_request=appointment_request)
            appointment_request.appointment = appointment

        context = {
            "appointment_request": appointment_request,
        }
        return render(request, self.template_name, context=context)

    def post(self, request, *args, **kwargs):
        appointment_request_id = kwargs.get('pk')
        appointment_request = get_object_or_404(
            AppointmentRequest, 
            id=appointment_request_id,
            is_deleted=False,
            is_active=True
        )

        # Check if user has permission to edit this appointment
        admin_clinics = ClinicDoctor.get_admin_clinics(request.user.doctors.id).values_list('clinic', flat=True)

        if not (appointment_request.clinic in admin_clinics or appointment_request.doctor.user == request.user):
            logger.error("You don't have permission to edit this appointment.")
            messages.error(request=request, message="You don't have permission to edit this appointment.")
            return redirect(self.success_url)

        # Update appointment fields from form data
        try:
            # Use atomic transaction to ensure data integrity
            with transaction.atomic():

                appointment_request.height = request.POST.get('height')
                appointment_request.weight = request.POST.get('weight')

                # Update date and time
                date_str = request.POST.get('date')
                start_time_str = request.POST.get('start_time')
                end_time_str = request.POST.get('end_time')

                if date_str and start_time_str and end_time_str:
                    # Parse date and time
                    appointment_request.date = get_date_obj(date_str)
                    appointment_request.start_time = get_time_obj(start_time_str)
                    appointment_request.end_time = get_time_obj(end_time_str)

                if Appointment.objects.filter(appointment_request=appointment_request).exists():
                    appointment = appointment_request.appointment
                    appointment.comment = request.POST.get('comment')
                    if not request.POST.get('amount_to_pay', '') == '':
                        appointment.amount_to_pay = request.POST.get('amount_to_pay')
                    if request.POST.get('amount_to_pay', '') in ['0', '0.00', '']:
                        appointment.appointment_status = 'payment_pending'
                    else:
                        appointment.appointment_status = 'paid'
                        appointment.paid = True
                    appointment.save()
                    appointment_request.save()
                else:
                    appointment_request.appointment_request_status = 'completed'
                    appointment_request.save()

                    appointment = Appointment.objects.filter(appointment_request=appointment_request.id).first()
                    appointment.comment = request.POST.get('comment')
                    if not request.POST.get('amount_to_pay', '') == '':
                        appointment.amount_to_pay = request.POST.get('amount_to_pay')
                    if request.POST.get('amount_to_pay', '') in ['0', '0.00', '']:
                        appointment.appointment_status = 'payment_pending'
                    else:
                        appointment.appointment_status = 'paid'
                        appointment.paid = True
                    appointment.save()

                messages.success(request=request, message="Appointment updated successfully.")
                return redirect(self.success_url)
        except Exception as e:
            logger.error(f"Error updating appointment: {str(e)}")
            messages.error(request=request, message=f"Error updating appointment: {str(e)}")
            return redirect(reverse_lazy("template_appointment:appointment_update", kwargs={'pk': appointment_request_id}))


class AppointmentCreateView(BaseETHView):
    template_name = "appointment/add-appointment.html"
    success_url = reverse_lazy("template_appointment:appointments_list")

    def get(self, request, *args, **kwargs):
        # Get user's clinics for the form
        admin_clinics = ClinicDoctor.get_admin_clinics(request.user.doctors.id)

        context = {
            "admin_clinics": admin_clinics,
        }
        return render(request, self.template_name, context=context)

    def post(self, request, *args, **kwargs):
        try:
            # Get form data
            clinic_id = request.POST.get('clinic')
            doctor_id = request.POST.get('doctor')
            name = request.POST.get('name')
            phone = request.POST.get('phone')
            date_str = request.POST.get('date')

            height = request.POST.get('height')
            weight = request.POST.get('weight')

            # Validate required fields
            if not all([clinic_id, doctor_id, name, phone]):
                logger.error("All required fields must be filled.")
                messages.error(request=request, message="All required fields must be filled.")
                return redirect(self.success_url)

            # Get clinic and doctor objects
            clinic = get_object_or_404(Clinic, id=clinic_id, is_deleted=False)
            doctor = get_object_or_404(Doctor, id=doctor_id, is_deleted=False)

            # Parse date
            date_obj = get_date_obj(date_str)
            if not date_obj:
                date_obj = get_today_date_obj()
                return redirect(self.success_url)

            # Set start and end time
            # TODO: Replace with actual logic to get available time slots
            start_time = get_now_time_obj()
            end_time = (datetime.datetime.combine(date_obj, start_time) + datetime.timedelta(minutes=30)).time()

            # Generate request token
            request_token = 1
            appointment_request = AppointmentRequest.objects.filter(clinic=clinic_id).order_by('-created_at').first()
            if appointment_request:
                try:
                    request_token = appointment_request.generate_next_request_token()
                except Exception as e:
                    logger.error(f"Error generating request token: {str(e)}")
                    raise ValueError(f"Error generating request token: {str(e)}")

            # Create appointment request
            appointment_request = AppointmentRequest.objects.create(
                name=name,
                phone=phone,
                date=date_obj,
                start_time=start_time,
                end_time=end_time,
                clinic=clinic,
                doctor=doctor,
                request_token=request_token,
                height=height,
                weight=weight,
            )

            messages.success(request=request, message="Appointment created successfully.")
            return redirect(self.success_url)
        except Exception as e:
            logger.error(f"Error creating appointment: {str(e)}")
            messages.error(request=request, message=f"Error creating appointment: {str(e)}")
            return redirect(self.success_url)


class AppointmentDeleteView(BaseETHView):
    suceess_url = reverse_lazy("template_appointment:appointments_list")

    def get(self, request, *args, **kwargs):
        appointment_request_id = kwargs.get('pk')
        appointment_request = get_object_or_404(
            AppointmentRequest, 
            id=appointment_request_id,
            is_deleted=False,
            is_active=True
        )

        # Check if user has permission to delete this appointment
        admin_clinics = ClinicDoctor.get_admin_clinics(request.user.doctors.id).values_list('clinic', flat=True)

        if not (appointment_request.clinic.id in admin_clinics or appointment_request.doctor.user == request.user):
            logger.error("You don't have permission to delete this appointment.")
            messages.error(request=request, message="You don't have permission to delete this appointment.")
            return redirect(self.suceess_url)

        # Use atomic transaction to ensure data integrity
        with transaction.atomic():
            # Mark the appointment request as deleted
            appointment_request.delete()

            # If the appointment exists, delete it as well
            if appointment_request.appointment:
                appointment_request.appointment.delete()

        messages.success(request=request, message="Appointment deleted successfully.")
        return redirect(self.suceess_url)   
