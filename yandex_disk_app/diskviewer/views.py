import requests
from django.shortcuts import render
from django.http import FileResponse, Http404
from django.views import View


class FileListView(View):
    def get(self, request):
        public_key = request.GET.get('public_key', '')
        path = request.GET.get('path', '')

        if not public_key:
            return render(request, 'diskviewer/index.html', {'error': 'Please provide a public key.'})

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

            if '_embedded' in data and 'items' in data['_embedded']:
                files = data['_embedded']['items']
                return render(request, 'diskviewer/file_list.html', {'files': files, 'public_key': public_key})
            else:
                return render(request, 'diskviewer/index.html', {'error': 'No files found.'})

        except requests.exceptions.RequestException as e:
            return render(request, 'diskviewer/index.html', {'error': str(e)})

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
