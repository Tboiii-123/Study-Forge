from django.urls import path
from . import views

urlpatterns = [
    path('entries/<int:entry_id>/study-pack/', views.create_study_pack, name='create_study_pack'),
    path('entries/<int:entry_id>/study-pack/status/', views.get_study_pack, name='get_study_pack'),
]