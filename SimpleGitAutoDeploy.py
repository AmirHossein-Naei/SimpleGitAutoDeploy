import json
import sys
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from subprocess import call
from urllib.parse import urlparse

class SimpleGitAutoDeploy(BaseHTTPRequestHandler):

    config = None

    @classmethod
    def get_config(cls):
        if cls.config is None:
            with open('config.json') as f:
                cls.config = json.load(f)

            for repository in cls.config.get('repositories', []):
                path = repository.get('path', '')
                if not os.path.isdir(path):
                    sys.exit(f'Directory {path} not found')
                if not os.path.isdir(os.path.join(path, '.git')) and \
                not os.path.isdir(os.path.join(path, 'objects')):
                    sys.exit(f'Directory {path} is not a Git repository')

        return cls.config


    def do_POST(self):
        event = self.headers.get('X-Github-Event')
        if event == 'ping':
            print('Ping event received')
            self.respond(204)
            return
        if event != 'push':
            print('We only handle ping and push events')
            self.respond(304)
            return

        self.respond(204)

        urls = self.parse_request()
        for url in urls:
            paths = self.get_matching_paths(url)
            for path in paths:
                print(f"Processing repository at URL: {url}")
                self.fetch(path)
                self.deploy(path)


    def parse_request(self):
        content_length = int(self.headers.get('content-length'))
        body = self.rfile.read(content_length)
        payload = json.loads(body)
        branch = payload.get('ref', '')
        repository_url = payload.get('repository', {}).get('url', '')
        self.branch = branch
        return [repository_url]


    def get_matching_paths(self, repo_url):
        matching_paths = []
        config = self.get_config()
        for repository in config.get('repositories', []):
            if repository.get('url') == repo_url:
                matching_paths.append(repository.get('path'))
        return matching_paths


    def respond(self, code):
        self.send_response(code)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()

    def fetch(self, path):
        print("Received post-push request.")
        print(f"Updating {path}...")
        try:
            call(f'cd "{path}" && git pull origin master', shell=True)
            print(f"Successfully updated {path}.")
        except Exception as e:
            print(f"Failed to update {path}: {e}")


    def deploy(self, path):
        config = self.get_config()
        for repository in config.get('repositories', []):
            if repository.get('path') == path and 'deploy' in repository:
                branch = repository.get('branch')
                if branch is None or branch == self.branch:
                    print('Executing deploy command')
                    call(f'cd "{path}" && {repository["deploy"]}', shell=True)
                else:
                    print(f'Push to different branch ({branch} != {self.branch}), not deploying')
                break

def main():
    server = None
    try:
        print("SimpleGitAutoDeploy is starting...")

        config = SimpleGitAutoDeploy.get_config()
        server_address = ('localhost', config.get('port', 8080))
        server = HTTPServer(server_address, SimpleGitAutoDeploy)
        print(f"Server listening on port {server_address[1]}")
        server.serve_forever()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if server is not None:
            server.socket.close()


if __name__ == '__main__':
    main()
