from .views import *
from django.conf.urls import re_path

app_name = 'webshop'

urlpatterns = [
    re_path(r'^payment/$',
            payment,
            name='payment'),
]
