from django.shortcuts import render
from django.http import HttpResponseRedirect
from .forms import paymentForm

def payment(request, template_name='payment.html'):

    ctx = {}
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = paymentForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            email = form.cleaned_data['email']
            webID = form.cleaned_data['webID']
            peppolID = form.cleaned_data['peppolID']
            # ...
            # redirect to a new URL:
            return HttpResponseRedirect('/thanks/')

    # if a GET (or any other method) we'll create a blank form
    else:
        form = paymentForm()

    ctx['form'] = form
    return render(request,template_name,ctx)
