from abc import ABC, abstractmethod

from apps.clinic.models import ClinicUserRole


class ETHealthBasePermission(ABC):

    @abstractmethod
    def has_permission(self, request):
        pass


class AllowAllClinicUsers(ETHealthBasePermission):

    def has_permission(self, request):
        clinic_users = request.user.clinic_users.filter(clinic_id=request.session.get('clinic_id'), user=request.user).first()
        if clinic_users:
            return True

        return False


class ClinicAdminPermission(ETHealthBasePermission):

    def has_permission(self, request):
        clinic_user = request.user.clinic_users.filter(clinic_id=request.session.get('clinic_id'), is_admin=True, user=request.user).first()
        if clinic_user:
            return True

        return False


# class DoctorPermission(ETHealthBasePermission):

#     def has_permission(self, request):
#         clinic_user = request.user.clinic_users.filter(clinic_id=request.session.get('clinic_id'), is_admin=False, role=ClinicUserRole.DOCTOR, user=request.user).first()
#         if clinic_user:
#             return True

#         return False


# class VisitingDoctorPermission(ETHealthBasePermission):

#     def has_permission(self, request):
#         clinic_user = request.user.clinic_users.filter(clinic_id=request.session.get('clinic_id'), is_admin=False, role=ClinicUserRole.VISITING_DOCTOR, user=request.user).first()
#         if clinic_user:
#             return True

#         return False


# class StaffPermission(ETHealthBasePermission):

#     def has_permission(self, request):
#         clinic_user = request.user.clinic_users.filter(clinic_id=request.session.get('clinic_id'), is_admin=False, role=ClinicUserRole.STAFF, user=request.user).first()
#         if clinic_user:
#             return True

#         return False
