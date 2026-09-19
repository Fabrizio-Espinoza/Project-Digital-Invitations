from django.urls import path
from . import views

app_name = "invitaciones"

urlpatterns = [
    path("<slug:slug>/", views.detalle_invitacion, name="detalle"),
    path("<slug:slug>/rsvp/", views.enviar_confirmacion, name="rsvp"),
    path("<slug:slug>/rsvp/conteo/", views.conteo_confirmados, name="conteo"),
]
