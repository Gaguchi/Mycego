import requests
import zipfile
from io import BytesIO
from django.shortcuts import render
from django.http import FileResponse, Http404
from django.views import View
from django.core.cache import cache


class FileListView(View):
    def get(self, request):
        public_key = request.GET.get('public_key', '')
        path = request.GET.get('path', '')
        file_type = request.GET.get('file_type', '')

        if not public_key:
            return render(request, 'diskviewer/index.html', {'error': 'Please provide a public key.'})

        cache_key = f'file_list_{public_key}_{path}'
        data = cache.get(cache_key)

        if not data:
            try:
                # Fetch the file list from Yandex Disk using OAuth
                headers = {
                    'Accept': 'application/json',
                }
                response = requests.get(
                    f'https://cloud-api.yandex.net/v1/disk/public/resources?public_key={public_key}&path={path}',
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()
                cache.set(cache_key, data, timeout=60*5)  # Cache for 5 minutes

            except requests.exceptions.RequestException as e:
                return render(request, 'diskviewer/index.html', {'error': str(e)})

        if '_embedded' in data and 'items' in data['_embedded']:
            files = data['_embedded']['items']
            if file_type:
                files = [file for file in files if file['type'] == file_type]
            return render(request, 'diskviewer/file_list.html', {'files': files, 'public_key': public_key})
        else:
            return render(request, 'diskviewer/index.html', {'error': 'No files found.'})
        
class DownloadFileView(View):
    def get(self, request):
        public_key = request.GET.get('public_key', '')
        file_path = request.GET.get('file_path', '')
        
        if not public_key or not file_path:
            return Http404("File not found.")
        
        try:
            # Fetch the download link for the file from Yandex Disk using OAuth
            headers = {
                'Accept': 'application/json',
                'Authorization': f'OAuth {OAUTH_TOKEN}',
            }
            response = requests.get(
                f'https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key={public_key}&path={file_path}',
                headers=headers
            )
            response.raise_for_status()
            download_link = response.json().get('href')

            # Download the file from the provided link
            file_response = requests.get(download_link, stream=True)
            file_response.raise_for_status()

            return FileResponse(file_response.raw, as_attachment=True, filename=file_path.split('/')[-1])

        except requests.exceptions.RequestException as e:
            return Http404("Error downloading the file: " + str(e))

class DownloadMultipleFilesView(View):
    def post(self, request):
        public_key = request.POST.get('public_key', '')
        file_paths = request.POST.getlist('file_paths')

        if not public_key or not file_paths:
            return render(request, 'diskviewer/index.html', {'error': 'Please provide a public key and select files to download.'})

        try:
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                for file_path in file_paths:
                    headers = {
                        'Accept': 'application/json',
                    }
                    response = requests.get(
                        f'https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key={public_key}&path={file_path}',
                        headers=headers
                    )
                    response.raise_for_status()
                    download_url = response.json()['href']
                    file_response = requests.get(download_url)
                    file_response.raise_for_status()
                    zip_file.writestr(file_path, file_response.content)

            zip_buffer.seek(0)
            response = FileResponse(zip_buffer, as_attachment=True, filename='files.zip')
            return response

        except requests.exceptions.RequestException as e:
            return render(request, 'diskviewer/index.html', {'error': str(e)})