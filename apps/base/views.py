
from django.shortcuts import render
from django.views.generic import TemplateView

from apps.base.permissions import ETHealthBasePermission

class DashboardView(TemplateView):
    template_name = "dashboard.html"
    permission_required = [ETHealthBasePermission]

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)