from django import forms        xml = self.cleaned_data['xml']

from django.utils.translation import gettext_lazy as _

class paymentForm(forms.Form):

    address =  forms.CharField(label=_('Address '))
