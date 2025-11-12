from rest_framework import viewsets, mixins, permissions
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed, ValidationError

from apps.appointment.models import AppointmentRequest, Appointment
from apps.appointment.serializers import AppointmentRequestSerializer
from apps.base.helpers import EncryptionDecryption
from apps.clinic.models import Clinic


class AppointmentRequestViewset(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin,
                                viewsets.GenericViewSet):
    queryset = AppointmentRequest.objects.all()
    serializer_class = AppointmentRequestSerializer
    filterset_fields = ['name', 'clinic']

    def filter_queryset(self, queryset):
        api_key = self.request.headers.get('x-api-key')
        enc_dec = EncryptionDecryption(data=api_key)
        clinic_id = enc_dec.decrypt()
        return queryset.filter(clinic=clinic_id)

    def perform_create(self, serializer):
        api_key = self.request.headers.get('x-api-key')
        if not api_key:
            raise ValidationError({"message": "API key is required", "error": True})

        try:
            enc_dec = EncryptionDecryption(data=api_key)
            clinic_id = enc_dec.decrypt()
            if not clinic_id:
                raise ValueError("Invalid clinic ID")
        except Exception:
            raise AuthenticationFailed({"message": "Invalid API key", "error": True})

        serializer.save(clinic_id=clinic_id)

    def create(self, request, *args, **kwargs):
        try:
            response = super().create(request, *args, **kwargs)
            return Response({
                "message": f"Token number for your appointment is {response.data.get('request_token')}",
                "token": response.data.get('request_token')
            }, status=response.status_code, headers=response.headers)
        except Exception as e:
            return Response({
                "message": f"Failed to generate appointment request: {str(e)}",
                "token": None,
                "error": True
            }, status=400)


class TokenViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]

    def list(self, request, *args, **kwargs):
        api_key = request.headers.get('x-api-key')
        if not api_key:
            raise ValidationError({"message": "API key is required", "error": True})

        try:
            enc_dec = EncryptionDecryption(data=api_key)
            clinic_id = enc_dec.decrypt()
            if not clinic_id:
                raise ValueError("Invalid clinic ID")
        except Exception:
            raise AuthenticationFailed({"message": "Invalid API key", "error": True})

        try:
            clinic = Clinic.objects.get(id=clinic_id)
        except Clinic.DoesNotExist:
            return Response({'error': 'Clinic not found'}, status=404)

        latest_appointment = Appointment.objects.filter(appointment_request__clinic=clinic).order_by('-created_at').first()
        current_token = latest_appointment.appointment_request.clinic.current_token_number if latest_appointment else 0

        return Response({'last_booked_token': latest_appointment.appointment_request.request_token, 'current_token': current_token})