import logging
from django.contrib.auth import logout
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views import View
from django.db import transaction

from apps.base.helpers import set_request_session_values
from apps.clinic.models import ClinicUser, ClinicUserRole
from apps.users.models import User, OTP
from django.contrib.auth import login
from ethealth.settings import OTP_RETRY_LIMIT
from django.contrib.auth.mixins import LoginRequiredMixin

from apps.users.models import User
from apps.clinic.models import ClinicUser
from apps.users.forms import UserProfileForm

logger = logging.getLogger(__name__)

login_template = "auth/login.html"
login_otp_template = "auth/login-otp.html"


class LoginView(View):

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            redirect_url = reverse_lazy("dashboard")
            if request.GET.get('next'):
                redirect_url = request.GET.get('next')
            return redirect(redirect_url)
        return render(request, login_template)


class OTPView(View):

    def get(self, request, *args, **kwargs):
        return redirect(reverse_lazy("template_user:login"))

    def post(self, request, *args, **kwargs):
        try:
            phone = request.POST.get('phone')
            logger.debug(f"Login request from {phone} phone")

            user_instance = User.objects.filter(phone_number=phone).first()
            if not user_instance:
                logger.debug(f"Mobile({phone}) not found in database")
                messages.error(request=request, message='No user found with given mobile number.')
                return redirect(reverse_lazy('template_user:login'))

            clinic_user_instance = ClinicUser.objects.filter(user=user_instance)
            if not clinic_user_instance:
                logger.debug(f"Mobile({phone}) is not clinic_user.")
                messages.error(request=request, message='Not allowed to login.')
                return redirect(reverse_lazy('template_user:login'))

            logger.debug(f"Mobile({phone}) found in database")
            otp_instance, otp_created = OTP.objects.get_or_create(user=user_instance)

            # Generate OTP and update user record
            otp, verification_string = otp_instance.generate_and_send_otp()
            logger.debug(f"OTP({otp}) generated successfully for user({user_instance.phone_number})")
            messages.success(request=request, message="OTP generated successfully.")

            return render(request, login_otp_template, context={"verification_string": verification_string, "phone": phone})

        except Exception as ex:
            logger.error(f"Login request from {phone} phone has been failed due to {str(ex)}")
            logger.exception(ex)
            messages.error(request=request, message="An error occurred.")
            return render(request, login_template)


class OTPVerifyView(View):

    def get(self, request, *args, **kwargs):
        return redirect(reverse_lazy("template_user:login"))

    def post(self, request, *args, **kwargs):

        if request.user.is_authenticated:
            return redirect(reverse_lazy("dashboard"))

        verification_string = request.POST['verification_string']
        phone = request.POST['phone']

        user_instance = User.objects.filter(phone_number=phone).first()
        if not user_instance:
            logger.debug(f"Mobile({phone}) not found in database")
            messages.error(request=request, message='No user found with given mobile number.')
            return redirect(reverse_lazy('template_user:login'))

        clinic_user_instance = ClinicUser.objects.filter(user=user_instance)
        if not clinic_user_instance:
            logger.debug(f"Mobile({phone}) is not clinic_user.")
            messages.error(request=request, message='Not allowed to login.')
            return redirect(reverse_lazy('template_user:login'))

        context = {
            "phone": request.POST['phone'],
            "verification_string": verification_string
        }
        otp = request.POST['otp']
        logger.debug(f"Verification request processing for OTP({otp}) and verification_string({verification_string}")
        try:
            otp_instance = OTP.objects.get(verification_string=verification_string)
        except OTP.DoesNotExist:
            messages.error(request=request, message="Please generate OTP.")
            return render(request, login_otp_template)

        if otp_instance.otp == str(otp) and otp_instance.is_valid():
            login(request, otp_instance.user)
            redirect_url = reverse_lazy("dashboard")
            if request.GET.get('next'):
                redirect_url = request.GET.get('next')
            otp_instance.otp_expiry = None
            otp_instance.verification_string = None
            otp_instance.max_otp_try = 0
            otp_instance.save()
            messages.success(request=request, message="User logged-in successfully.")

            # check user is admin of clinic or not
            user_id = otp_instance.user.id
            # First check if user is admin of any clinic
            clinic_user = ClinicUser.get_admin_clinics(user_id=user_id).first()
            # if not clinic_user:
            #     # Check if user is doctor
            #     clinic_user = ClinicUser.get_active_clinic_users(user_id=user_id, role=ClinicUserRole.DOCTOR.value).first()
            # if not clinic_user:
            #     # Check if user is visitor doctor
            #     clinic_user = ClinicUser.get_active_clinic_users(user_id=user_id, role=ClinicUserRole.VISITING_DOCTOR.value).first()
            if not clinic_user:
                # check if user is admin member at any club
                clinic_user = ClinicUser.get_active_clinic_users(user_id=user_id, role=ClinicUserRole.ADMIN.value).first()
            if not clinic_user:
                # check if user is staff member at any club
                clinic_user = ClinicUser.get_active_clinic_users(user_id=user_id, role=ClinicUserRole.STAFF.value).first()

            if not clinic_user:
                raise Exception("This user is not associated with any clinic.")

            set_request_session_values(request=request, clinic_id=clinic_user.clinic.id)
            return redirect(redirect_url)

        if not otp_instance.is_valid():
            logger.info("OTP timed out.")
            otp, verification_string = otp_instance.generate_and_send_otp()
            messages.success(request=request, message="Successfully generated OTP.")

        if otp_instance.otp != otp:
            logger.info("Max otp try reached. Creating new otp.")
            otp, verification_string = otp_instance.generate_and_send_otp()
            messages.success(request=request, message="Successfully generated new OTP.")

        if otp_instance.otp != otp:
            logger.info("Invalid otp but max retry limit is not reached.")
            otp_instance.max_otp_try = int(otp_instance.max_otp_try) + 1
            otp_instance.save()
            messages.error(request=request, message="Invalid otp. Try again.")

        return render(request, login_otp_template, context=context)


class LogoutView(View):

    success_url = reverse_lazy("template_user:login")

    def get(self, request, *args, **kwargs):
        is_force_logout = request.GET.get('force_logout') == 'true'
        if is_force_logout:
            request.user.remove_all_active_sessions()
        else:
            logout(request)
        messages.success(request=request, message="Logged out successfully.")
        return redirect(self.success_url)

class UserProfileView(LoginRequiredMixin, View):
    template_name = 'user/profile.html'
    login_url = reverse_lazy('template_user:login')

    def get(self, request, *args, **kwargs):
        user = request.user
        print(f"************* user: {user} ****************")
        try:
            clinic_user = ClinicUser.objects.get(
                user=user,
                clinic_id=request.session.get('clinic_id')
            )
            context = {
                'user': user,
                'clinic_user': clinic_user,
                'address': clinic_user.address if clinic_user.address else {}
            }
            return render(request, self.template_name, context)
        except ClinicUser.DoesNotExist:
            messages.error(request, "Clinic user profile not found.")
            return redirect('dashboard')


class UserProfileUpdateView(LoginRequiredMixin, View):
    template_name = 'user/profile_update.html'
    login_url = reverse_lazy('template_user:login')

    def get(self, request, *args, **kwargs):
        user = request.user
        try:
            clinic_user = ClinicUser.objects.get(
                user=user,
                clinic_id=request.session.get('clinic_id')
            )
            form = UserProfileForm(instance=clinic_user)
            context = {
                'form': form,
                'user': user,
                'clinic_user': clinic_user,
                'address': clinic_user.address if clinic_user.address else {}
            }
            return render(request, self.template_name, context)
        except ClinicUser.DoesNotExist:
            messages.error(request, "Clinic user profile not found.")
            return redirect('dashboard')

    def post(self, request, *args, **kwargs):
        user = request.user
        try:
            clinic_user = ClinicUser.objects.get(
                user=user,
                clinic_id=request.session.get('clinic_id')
            )

            if request.method == 'POST':
                with transaction.atomic():
                    # Update clinic user details
                    clinic_user.name = request.POST.get('name', clinic_user.name)
                    clinic_user.date_of_birth = request.POST.get('date_of_birth') or None
                    clinic_user.gender = request.POST.get('gender') or None
                    
                    # Handle age - either from manual input or calculated from date of birth
                    manual_age = request.POST.get('age')
                    if manual_age and manual_age.strip():
                        # Use manually entered age
                        clinic_user.age = int(manual_age)
                    elif clinic_user.date_of_birth:
                        # Calculate age from date of birth if no manual age provided
                        from datetime import date
                        today = date.today()
                        dob = clinic_user.date_of_birth
                        if isinstance(dob, str):
                            from datetime import datetime
                            dob = datetime.strptime(dob, '%Y-%m-%d').date()
                        
                        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                        clinic_user.age = age

                    # Handle address fields
                    address = {}
                    address_fields = ['line1', 'city', 'state', 'country', 'postal_code']
                    for field in address_fields:
                        form_field = f'address_{field}'
                        field_value = request.POST.get(form_field, '').strip()
                        if field_value:
                            address[field] = field_value
                    
                    # Only save address if at least one field has a value, otherwise save empty dict
                    clinic_user.address = address if any(address.values()) else {}
                    clinic_user.save()

                    # Handle avatar upload
                    if 'avatar' in request.FILES:
                        # Note: User model doesn't have avatar field yet
                        # This would need to be added to the User model
                        pass

                messages.success(request, "Profile updated successfully.")
                return redirect('template_user:user_profile')
            
        except ClinicUser.DoesNotExist:
            messages.error(request, "Clinic user profile not found.")
            return redirect('dashboard')
        except Exception as e:
            messages.error(request, f"An error occurred while updating profile: {str(e)}")
            return redirect('template_user:user_profile_update')