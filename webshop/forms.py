from django import forms

from django.utils.translation import gettext_lazy as _

class paymentForm(forms.Form):

    address =  forms.CharField(label=_('Address ') , widget=forms.TextInput(attrs={'placeholder': 'WebID-PeppolID-Email'}))
