from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib import messages
from django.urls import reverse_lazy
from django.db import transaction

from apps.clinic.forms import ClinicDetailsForm
from apps.clinic.models import Clinic


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
