from django.urls import path, include
from rest_framework import routers

from apps.appointment.views.api_views import AppointmentRequestViewset,TokenViewSet 

default_router = routers.DefaultRouter()

default_router.register("request", AppointmentRequestViewset, "appointment-request")
default_router.register("token", TokenViewSet, basename="token")

# API urls
urlpatterns = [
     path("", include(default_router.urls)),
]
