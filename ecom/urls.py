from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path , include
from main.views import IndexPageView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', view=IndexPageView, name='index'),
    path('procurement/', include('procurement.urls') , name = 'procurement'),

]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
