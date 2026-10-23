"""
Minimal ServiceNow Table API client.

Credentials come from the environment, never from source code:
  SNOW_INSTANCE_URL  e.g. https://dev12345.service-now.com
  SNOW_USER          your PDI user name
  SNOW_PASSWORD      your PDI password

Only the calls this project needs are implemented: find and create on a table.
"""
import os

import requests


class SnowClient:
    def __init__(self, instance_url=None, user=None, password=None,
                 session=None, timeout=30):
        self.base = (instance_url or os.environ["SNOW_INSTANCE_URL"]).rstrip("/")
        self.auth = (user or os.environ["SNOW_USER"],
                     password or os.environ["SNOW_PASSWORD"])
        self.session = session or requests.Session()
        self.timeout = timeout

    def _url(self, table):
        return f"{self.base}/api/now/table/{table}"

    def find(self, table, query, fields="sys_id,number,short_description,state,urgency,impact"):
        """Return up to 10 records matching an encoded query such as 'active=true'."""
        resp = self.session.get(
            self._url(table),
            auth=self.auth,
            headers={"Accept": "application/json"},
            params={"sysparm_query": query, "sysparm_fields": fields, "sysparm_limit": 10},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["result"]

    def create(self, table, payload):
        """Create one record and return it, including its number."""
        resp = self.session.post(
            self._url(table),
            auth=self.auth,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["result"]
