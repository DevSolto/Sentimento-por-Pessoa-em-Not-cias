from __future__ import annotations

import time
from typing import Dict

import requests


class HttpClient:
    def __init__(self, headers: Dict[str, str]):
        self.session = requests.Session()
        self.session.headers.update(headers)

    def fetch(self, url: str, *, timeout: int = 20) -> requests.Response:
        for attempt in range(4):
            try:
                resp = self.session.get(url, timeout=timeout)
                if resp.status_code >= 500:
                    raise requests.HTTPError(f"Status {resp.status_code}")
                return resp
            except Exception as e:
                if attempt == 3:
                    raise e
                time.sleep(1.0)

