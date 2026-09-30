"""
URL configuration for invitaciones_core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from invitaciones import views as vistas_invitaciones

urlpatterns = [
    # la ruta del admin sale de settings (en producción se cambia en el .env)
    path(settings.ADMIN_URL, admin.site.urls),
    path('invitaciones/', include('invitaciones.urls')),
    path('', vistas_invitaciones.catalogo, name='catalogo'),
    path('pedido/<str:token>/', vistas_invitaciones.pedido, name='pedido'),
    path('pedido/<str:token>/vista/', vistas_invitaciones.pedido_vista_previa, name='pedido_vista_previa'),
    path('panel/<str:token>/', vistas_invitaciones.panel_anfitrion, name='panel_anfitrion'),
    path('panel/<str:token>/lista.csv', vistas_invitaciones.panel_lista_csv, name='panel_lista_csv'),
    path('panel/<str:token>/revelar/', vistas_invitaciones.panel_revelar, name='panel_revelar'),
    path('privacidad/', vistas_invitaciones.aviso_privacidad, name='aviso_privacidad'),
]

# En desarrollo, runserver sirve también las fotos subidas (media/).
# En producción esto lo hace el servidor web, no Django.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
