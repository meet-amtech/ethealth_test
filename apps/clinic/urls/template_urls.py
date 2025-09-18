from django.urls import path
from ..views.template_views import ClinicDetailsView

app_name = 'template_clinic'

urlpatterns = [
    # Clinic Details
    path('details/', ClinicDetailsView.as_view(), name='clinic_details'),
]
