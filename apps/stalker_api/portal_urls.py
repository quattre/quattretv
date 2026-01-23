"""
URLs for portal.php compatible endpoint.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.portal_handler, name='portal'),
]
