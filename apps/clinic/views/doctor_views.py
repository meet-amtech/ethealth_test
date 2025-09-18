from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import UpdateView

from ..models import DoctorAvailability, ClinicUserRole, ClinicUser, WeekDay, Clinic
from ..forms import DoctorAvailabilityForm


class DoctorAvailabilityView(View):
    """View for managing doctor availability"""
    template_name = 'clinic/doctor_availability.html'
    login_url = reverse_lazy('template_user:login')
    
    def get(self, request, *args, **kwargs):
        clinic_id = request.session.get('clinic_id')
        if not clinic_id:
            messages.error(request, "No clinic selected.")
            return redirect('dashboard')
        
        # Get all doctors for the clinic
        doctors = ClinicUser.objects.filter(
            clinic_id=clinic_id,
            role=ClinicUserRole.DOCTOR,
            is_active=True
        ).select_related('user')
        
        # Get or create availability for each day for each doctor
        weekdays = [day[0] for day in WeekDay.choices]
        availability_data = {}
        
        for doctor in doctors:
            doctor_availability = {}
            for day in weekdays:
                # Get or create availability for this doctor on this day
                availability, created = DoctorAvailability.objects.get_or_create(
                    doctor=doctor,
                    clinic_id=clinic_id,
                    weekday=day,
                    defaults={
                        'start_time': '09:00:00',
                        'end_time': '17:00:00',
                    }
                )
                doctor_availability[day] = availability
            availability_data[doctor] = doctor_availability
        
        context = {
            'weekdays': WeekDay.choices,
            'availability_data': availability_data,
            'doctors': doctors,
        }
        return render(request, self.template_name, context)


class DoctorAvailabilityUpdateView(UpdateView):
    """View for updating doctor availability"""
    model = DoctorAvailability
    form_class = DoctorAvailabilityForm
    template_name = 'clinic/doctor_availability_form.html'
    pk_url_kwarg = 'pk'
    
    def get_success_url(self):
        return reverse_lazy('doctor_availability:doctor_schedule')
    
    def form_valid(self, form):
        messages.success(self.request, "Schedule updated successfully.")
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)
