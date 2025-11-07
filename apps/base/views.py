
from django.shortcuts import render
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin


from apps.base.permissions import ETHealthBasePermission

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"
    permission_required = [ETHealthBasePermission]

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)