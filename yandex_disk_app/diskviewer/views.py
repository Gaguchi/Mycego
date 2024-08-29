import requests
import zipfile
import time
from io import BytesIO
from django.shortcuts import render
from django.http import FileResponse, Http404
from django.views import View
from django.core.cache import cache
from requests.exceptions import RequestException

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
            headers = {
                'Accept': 'application/json',
            }
            response = requests.get(
                f'https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key={public_key}&path={file_path}',
                headers=headers
            )
            response.raise_for_status()
            download_link = response.json().get('href')

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
            all_file_paths = []
            for file_path in file_paths:
                all_file_paths.extend(self.gather_file_paths(public_key, file_path))

            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                skipped_files = self.add_files_to_zip(zip_file, all_file_paths)

            zip_buffer.seek(0)
            response = FileResponse(zip_buffer, as_attachment=True, filename='files.zip')
            if skipped_files:
                response['Content-Disposition'] += f"; filename*=UTF-8''files_with_skipped.zip"
                response['X-Skipped-Files'] = ', '.join(skipped_files)
            return response

        except requests.exceptions.RequestException as e:
            return render(request, 'diskviewer/index.html', {'error': str(e)})

    def gather_file_paths(self, public_key, file_path, base_path=''):
        headers = {
            'Accept': 'application/json',
        }

        try:
            response = requests.get(
                f'https://cloud-api.yandex.net/v1/disk/public/resources?public_key={public_key}&path={file_path}',
                headers=headers
            )
            print(f"Response status code for {file_path}: {response.status_code}")
            print(f"Response content for {file_path}: {response.content}")
            response.raise_for_status()
            data = response.json()
        except RequestException as e:
            print(f"Error accessing {file_path}: {e}")
            raise e

        file_paths = []
        if data['type'] == 'dir':
            dir_name = f"{base_path}/{data['name']}" if base_path else data['name']
            for item in data['_embedded']['items']:
                item_path = item['path']
                relative_path = f"{dir_name}/{item['name']}"
                file_paths.extend(self.gather_file_paths(public_key, item_path, dir_name))
        else:
            download_response = requests.get(
                f'https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key={public_key}&path={file_path}',
                headers=headers
            )
            download_response.raise_for_status()
            download_url = download_response.json()['href']
            file_name = f"{base_path}/{data['name']}" if base_path else data['name']
            file_paths.append((file_name, download_url))

        return file_paths

    def add_files_to_zip(self, zip_file, file_paths):
        skipped_files = []
        for file_name, download_url in file_paths:
            try:
                file_response = requests.get(download_url)
                file_response.raise_for_status()
                print(f"Adding file to zip: {file_name}")  # Debug statement
                zip_file.writestr(file_name, file_response.content)
                time.sleep(1)  # Adding a delay of 1 second between requests
            except requests.exceptions.RequestException as e:
                if file_response.status_code == 429:
                    print(f"Skipping file due to download limit exceeded: {file_name}")
                    skipped_files.append(file_name)
                else:
                    print(f"Error downloading {file_name}: {e}")
                    print(f"Response content: {file_response.content}")
                    print(f"Response headers: {file_response.headers}")
            except Exception as e:
                print(f"Error adding {file_name} to zip: {e}")
        return skipped_files