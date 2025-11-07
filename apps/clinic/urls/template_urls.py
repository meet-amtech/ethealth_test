from django.urls import path
from ..views.template_views import (
    ClinicDetailsView, 
    OpeningHourListView, 
    DoctorOpeningHourCreateView,
    OpeningHourDeleteView,
    OpeningHourUpdateView
)

app_name = 'template_clinic'

urlpatterns = [
    # Clinic Details
    path('details/', ClinicDetailsView.as_view(), name='clinic_details'),
    path("opening-hours/", OpeningHourListView.as_view(), name="opening_hour_list"),
    path("opening-hours/create/", DoctorOpeningHourCreateView.as_view(), name="opening_hour_create"),
    path("opening-hours/<uuid:pk>/update/", OpeningHourUpdateView.as_view(), name="opening_hour_update"),
    path("opening-hours/<uuid:pk>/delete/", OpeningHourDeleteView.as_view(), name="opening_hour_delete"),
]
