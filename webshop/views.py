from django.shortcuts import render
from django.http import HttpResponseRedirect
from .forms import paymentForm
from django.contrib.auth.models import User
from accounts.models import Activation

def payment(request, template_name='payment.html'):

    ctx = {}

    if request.method == 'POST':
        form = paymentForm(request.POST)
        if form.is_valid():
            sender = User.objects.get(username='webshop')
            recipient_UWP = form.cleaned_data['address']

            xml_type = 'invoice'

            via = request.POST['via']
            if via=='AS4':
                peppol_classic = False
            else:
                peppol_classic = True

            try:
                recipient = Activation.objects.get(webID=recipient_UWP)
                recipient_username = recipient.user.username
                recipient = User.objects.get(username=recipient_username)
            except ObjectDoesNotExist:
                try:
                    recipient = Activation.objects.get(peppolID=recipient_UWP)
                    recipient_username = recipient.user.username
                    recipient = User.objects.get(username=recipient_username)
                except ObjectDoesNotExist:
                    try:
                        recipient = User.objects.get(username=recipient_UWP)
                        recipient_username = recipient.username
                    except ObjectDoesNotExist as e:
                        ctx["errors"] = ["%s" % e]
                        return render(request, template_name, ctx )

            recipient = User.objects.get(pk=recipient.pk)
            form.save(sender=request.user , recipient=recipient , xml_type=xml_type, peppol_classic = peppol_classic)
            messages.info(request, _(u"Message successfully sent."))
            if success_url is None:
                success_url = reverse_lazy('django_messages:messages_outbox')
            if 'next' in request.GET:
                success_url = request.GET['next']

            return HttpResponseRedirect(success_url)
    else:
        form = paymentForm()

    ctx['form'] = form
    return render(request,template_name,ctx)
