from django.shortcuts import render
from django.http import HttpResponseRedirect
from .forms import paymentForm

def payment(request, template_name='payment.html'):

    ctx = {}
    if request.method == 'POST':
        form = paymentForm(request.POST)

        if form.is_valid():
            address = form.cleaned_data['address']
            via = form.cleaned_data['via']
            return HttpResponseRedirect('/thanks/')

    else:
        form = paymentForm()

    ctx['form'] = form
    return render(request,template_name,ctx)
