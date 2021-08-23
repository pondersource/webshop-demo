from django.shortcuts import render
from django.views.generic import TemplateView

# Create your views here.
def IndexPageView(request,template_name = 'index.html'):

    ctx = {}
    if request.user.is_authenticated:
        ctx['requests_count'] = Contact.objects.unread_request_count(request.user)
    return render(request, template_name, ctx)
