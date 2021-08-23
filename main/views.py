from django.shortcuts import render
from django.views.generic import TemplateView

# Create your views here.
def IndexPageView(request,template_name = 'index.html'):

    return render(request, template_name)
