import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib import messages
from django.urls import reverse_lazy
from django.db import transaction

from apps.clinic.forms import ClinicDetailsForm, OpeningHourForm
from apps.clinic.models import Clinic, DoctorAvailability, WeekDay, ClinicUser, ClinicUserRole


logger = logging.getLogger(__name__)

class ClinicDetailsView(LoginRequiredMixin, View):
    """View for displaying and updating clinic details"""
    template_name = 'clinic/clinic_details.html'
    login_url = reverse_lazy('template_user:login')
    
    def get(self, request, *args, **kwargs):
        clinic_id = request.session.get('clinic_id')
        if not clinic_id:
            messages.error(request, "No clinic selected.")
            return redirect('dashboard')
        
        clinic = get_object_or_404(Clinic, id=clinic_id)
        form = ClinicDetailsForm(instance=clinic)
        
        context = {
            'clinic': clinic,
            'form': form,
        }
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        clinic_id = request.session.get('clinic_id')
        if not clinic_id:
            messages.error(request, "No clinic selected.")
            return redirect('dashboard')
        
        clinic = get_object_or_404(Clinic, id=clinic_id)
        form = ClinicDetailsForm(request.POST, instance=clinic)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    clinic = form.save()
                    # Update session with new clinic name
                    from apps.base.helpers import set_request_session_values
                    set_request_session_values(request, clinic_id=clinic.id)
                messages.success(request, "Clinic details updated successfully.")
                return redirect('template_clinic:clinic_details')
            except Exception as e:
                messages.error(request, f"An error occurred while updating clinic details: {str(e)}")
        else:
            messages.error(request, "Please correct the errors below.")
        
        context = {
            'clinic': clinic,
            'form': form,
        }
        return render(request, self.template_name, context)

class OpeningHourListView(LoginRequiredMixin, View):
    # permission_required = [AllowAllClinicUsers]
    template_name = 'setting/opening-hours.html'

    def get(self, request, *args, **kwargs):
        try:
            clinic_id = request.session.get('clinic_id')
            clinic = Clinic.objects.get(id=clinic_id)

            # Fetch all doctor availabilities for the clinic
            availabilities = DoctorAvailability.objects.filter(
                clinic=clinic,
                is_deleted=False,
                is_active=True
            ).select_related('doctor').order_by('weekday', 'start_time')

            # Group by time slots
            time_slots = {}
            all_days = set(WeekDay.values)
            used_days = set()

            for avail in availabilities:
                time_key = f"{avail.start_time.strftime('%H:%M')} - {avail.end_time.strftime('%H:%M')}"
                
                if time_key not in time_slots:
                    time_slots[time_key] = {
                        'start_time': avail.start_time.strftime('%H:%M'),
                        'end_time': avail.end_time.strftime('%H:%M'),
                        'break_start': avail.break_start.strftime('%H:%M') if avail.break_start else None,
                        'break_end': avail.break_end.strftime('%H:%M') if avail.break_end else None,
                        'days': [],
                        'availability_ids': [],  # Store all availability IDs for this time slot
                        'href_query_params': f"opening_hour={avail.start_time.strftime('%H:%M')}&closing_hour={avail.end_time.strftime('%H:%M')}&break_start={avail.break_start.strftime('%H:%M') if avail.break_start else ''}&break_end={avail.break_end.strftime('%H:%M') if avail.break_end else ''}",
                    }
                
                # Add the availability ID to the list
                time_slots[time_key]['availability_ids'].append(str(avail.id))
                
                day_name = WeekDay(avail.weekday).label
                time_slots[time_key]['days'].append(day_name)
                used_days.add(avail.weekday)

            # Get available days (not used in any time slot)
            available_days = [WeekDay(day).label for day in (all_days - used_days)]

            # Convert the time_slots dictionary to a format the template expects
            opening_hours_schedules = {}
            for i, slot in enumerate(time_slots.values()):
                opening_hours_schedules[f'slot_{i}'] = slot

            context = {
                'opening_hours_schedules': opening_hours_schedules,
                'is_day_available': bool(available_days)
            }
            return render(request, self.template_name, context)

        except Exception as e:
            logger.error(f"Failed to list opening hours: {str(e)}", exc_info=True)
            messages.error(request, "Failed to load opening hours. Please try again later.")
            return redirect(reverse_lazy("dashboard"))

class DoctorOpeningHourCreateView(LoginRequiredMixin, View):

    """View for creating doctor's opening hours"""
    login_url = reverse_lazy('template_user:login')
    template_name = 'setting/add-opening-hours.html'
    success_url = reverse_lazy('template_clinic:opening_hour_list')

    def get_doctor_user(self, clinic_id):
        """Get or create doctor user for the current user and clinic"""
        try:
            return ClinicUser.objects.get(
                user=self.request.user,
                clinic_id=clinic_id,
                role__in=[ClinicUserRole.DOCTOR, ClinicUserRole.ADMIN]
            )
        except Exception as e:
            messages.info(request, str(e))
            return redirect('dashboard')
            # Create a new ClinicUser if one doesn't exist
            

    def get_available_days(self, clinic_id, doctor_user_id):
        """Get days that don't have availability set yet"""
        existing_days = set(DoctorAvailability.objects.filter(
            clinic_id=clinic_id,
            doctor_id=doctor_user_id,
            is_deleted=False
        ).values_list('weekday', flat=True))
        
        return [
            (day.value, day.label)
            for day in WeekDay
            if day.value not in existing_days
        ]

    def get(self, request, *args, **kwargs):
        try:
            clinic_id = request.session.get('clinic_id')
            if not clinic_id:
                messages.error(request, "No clinic selected.")
                return redirect('dashboard')

            doctor_user = self.get_doctor_user(clinic_id)
           
            available_days = self.get_available_days(clinic_id, doctor_user.id)

            return render(request, self.template_name, {
                'available_days': available_days,
                'weekdays': WeekDay.choices,
                'form': OpeningHourForm()
            })

        except Exception as e:
            logger.error(f"Failed to load opening hours form: {str(e)}", exc_info=True)
            messages.error(request, "Failed to load opening hours form.")
            return redirect(self.success_url)

    def post(self, request, *args, **kwargs):
        try:
            clinic_id = request.session.get('clinic_id')
            if not clinic_id:
                messages.error(request, "No clinic selected.")
                return redirect('dashboard')

            doctor_user = self.get_doctor_user(clinic_id)
            form = OpeningHourForm(request.POST)
            
            if not form.is_valid():
                available_days = self.get_available_days(clinic_id, doctor_user.id)
                return render(request, self.template_name, {
                    'form': form,
                    'available_days': available_days,
                    'weekdays': WeekDay.choices
                })

            selected_days = request.POST.getlist('selected_days', [])
            start_time = form.cleaned_data['start_time']
            end_time = form.cleaned_data['end_time']
            break_start = form.cleaned_data.get('break_start')
            break_end = form.cleaned_data.get('break_end')

            if start_time >= end_time:
                messages.error(request, "Start time must be before end time.")
                return redirect('template_clinic:opening_hour_create')

            if (break_start and not break_end) or (not break_start and break_end):
                messages.error(request, "Please provide both break start and end times or leave both empty.")
                return redirect('template_clinic:opening_hour_create')

            if break_start and break_end:
                if not (start_time <= break_start <= break_end <= end_time):
                    messages.error(request, "Break time must be within working hours.")
                    return redirect('template_clinic:opening_hour_create')

            with transaction.atomic():
                for day in selected_days:
                    DoctorAvailability.objects.update_or_create(
                        doctor=doctor_user,
                        clinic_id=clinic_id,
                        weekday=day,
                        defaults={
                            'start_time': start_time,
                            'end_time': end_time,
                            'break_start': break_start,
                            'break_end': break_end,
                            'updated_by': request.user
                        }
                    )

            messages.success(request, "Opening hours added successfully.")
            return redirect(self.success_url)

        except Exception as e:
            logger.exception(f"Error saving opening hours: {str(e)}")
            messages.error(request, "Failed to save opening hours. Please try again.")
            return redirect('template_clinic:opening_hour_create')


class OpeningHourUpdateView(LoginRequiredMixin, View):
    """View for updating doctor's opening hours"""
    login_url = reverse_lazy('template_user:login')
    template_name = 'setting/update-opening-hours.html'
    success_url = reverse_lazy('template_clinic:opening_hour_list')

    def get_doctor_user(self, clinic_id):
        """Get or create doctor user for the current user and clinic"""
        user = self.request.user
        doctor_user = ClinicUser.objects.get(
            user=user,
            clinic_id=clinic_id,
            role__in = [ClinicUserRole.DOCTOR.value, ClinicUserRole.ADMIN.value],
            is_active = True
            # defaults={
            #     'role': ClinicUserRole.DOCTOR.value,
            #     'is_primary': True,
            #     'is_active': True
            # }
        )
        return doctor_user

    def get(self, request, *args, **kwargs):
        try:
            clinic_id = request.session.get('clinic_id')
            if not clinic_id:
                messages.error(request, "No clinic selected.")
                return redirect('dashboard')

            # Get the availability record
            availability = get_object_or_404(
                DoctorAvailability,
                id=kwargs.get('pk'),
                clinic_id=clinic_id,
                is_deleted=False
            )

            # Get the form with initial data
            initial_data = {
                'start_time': availability.start_time.strftime('%H:%M'),
                'end_time': availability.end_time.strftime('%H:%M'),
                'break_start': availability.break_start.strftime('%H:%M') if availability.break_start else '',
                'break_end': availability.break_end.strftime('%H:%M') if availability.break_end else '',
                'selected_days': [availability.weekday]
            }
            form = OpeningHourForm(initial=initial_data)

            context = {
                'form': form,
                'weekdays': WeekDay.choices,
                'selected_day': availability.weekday,
                'availability_id': str(availability.id)
            }
            return render(request, self.template_name, context)

        except Exception as e:
            logger.error(f"Failed to load opening hour update form: {str(e)}", exc_info=True)
            messages.error(request, "Failed to load opening hour form. Please try again.")
            return redirect(self.success_url)

    def post(self, request, *args, **kwargs):
        try:
            clinic_id = request.session.get('clinic_id')
            if not clinic_id:
                messages.error(request, "No clinic selected.")
                return redirect('dashboard')

            # Get the availability record
            availability = get_object_or_404(
                DoctorAvailability,
                id=kwargs.get('pk'),
                clinic_id=clinic_id,
                is_deleted=False
            )

            # Get the form data
            form_data = request.POST.copy()
            
            # Convert single day selection to list if needed
            if 'selected_days' not in form_data:
                form_data.setlist('selected_days', [form_data.get('selected_days')])
            
            form = OpeningHourForm(form_data)
            
            if form.is_valid():
                try:
                    with transaction.atomic():
                        # Update the existing record
                        availability.start_time = form.cleaned_data['start_time']
                        availability.end_time = form.cleaned_data['end_time']
                        availability.break_start = form.cleaned_data['break_start'] or None
                        availability.break_end = form.cleaned_data['break_end'] or None
                        
                        # Get the first selected day (since we're updating a single record)
                        if form.cleaned_data['selected_days']:
                            availability.weekday = form.cleaned_data['selected_days'][0]
                        
                        availability.updated_by = request.user
                        availability.save()

                    messages.success(request, "Opening hour updated successfully.")
                    return redirect(self.success_url)
                    
                except Exception as e:
                    logger.error(f"Error updating opening hour: {str(e)}", exc_info=True)
                    messages.error(request, "An error occurred while updating the opening hour.")
            
            # If form is not valid or there was an error, show the form with errors
            context = {
                'form': form,
                'weekdays': WeekDay.choices,
                'selected_day': form.data.get('selected_days', [''])[0],
                'availability_id': str(availability.id)
            }
            return render(request, self.template_name, context)

        except Exception as e:
            logger.error(f"Failed to update opening hour: {str(e)}", exc_info=True)
            messages.error(request, "Failed to update opening hour. Please try again.")
            return redirect(self.success_url)


class OpeningHourDeleteView(LoginRequiredMixin, View):
    """View for deleting doctor's opening hours"""
    login_url = reverse_lazy('template_user:login')
    success_url = reverse_lazy('template_clinic:opening_hour_list')

    def post(self, request, *args, **kwargs):
        try:
            clinic_id = request.session.get('clinic_id')
            if not clinic_id:
                messages.error(request, "No clinic selected.")
                return redirect('dashboard')

            # Get the availability record
            availability = get_object_or_404(
                DoctorAvailability,
                id=kwargs.get('pk'),
                clinic_id=clinic_id,
                doctor__user=request.user,  # Ensure the user owns this record
                is_deleted=False
            )

            # Soft delete the record
            availability.is_deleted = True
            availability.is_active = False
            availability.updated_by = request.user
            availability.save()

            messages.success(request, "Opening hour deleted successfully.")
            return redirect(self.success_url)

        except Exception as e:
            logger.error(f"Failed to delete opening hour: {str(e)}", exc_info=True)
            messages.error(request, "Failed to delete opening hour. Please try again.")
            return redirect(self.success_url)