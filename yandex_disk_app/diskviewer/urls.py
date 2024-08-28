from django.urls import path
from .views import FileListView, DownloadFileView, DownloadMultipleFilesView

urlpatterns = [
    path('', FileListView.as_view(), name='file_list'),
    path('download/', DownloadFileView.as_view(), name='download_file'),
    path('download_multiple/', DownloadMultipleFilesView.as_view(), name='download_multiple_files'),
]
