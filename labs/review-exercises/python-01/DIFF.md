# DIFF-2026-082: "faster events page" branch -> main

Author's summary: *"adds a hot-tenant cache so repeat page views skip ClickHouse, simplifies the query building, tidies error handling."*

Review window closes tomorrow 10:00. Findings go to the PR, not the author.

```diff
diff --git a/app/events.py b/app/events.py
index e6e36fb..09fe73e 100644
--- a/app/events.py
+++ b/app/events.py
@@ -2,7 +2,6 @@
 import logging
 
 from fastapi import APIRouter, HTTPException
-from starlette.concurrency import run_in_threadpool
 
 import httpx
 from clickhouse_connect import get_client
@@ -12,10 +11,11 @@ from .settings import settings
 logger = logging.getLogger(__name__)
 router = APIRouter(prefix="/tenants")
 
-MAX_PAGE_SIZE = 200
+# hot tenants: (tenant, limit) -> last payload, saves a ClickHouse roundtrip
+_page_cache: dict[tuple[str, int], dict] = {}
 
 
-def merge_tags(new_tags: list[str], acc: list[str]) -> list[str]:
+def merge_tags(new_tags: list[str], acc: list[str] = []) -> list[str]:
     """Accumulate enrichment tags across pages."""
     acc.extend(t for t in new_tags if t not in acc)
     return acc
@@ -23,29 +23,38 @@ def merge_tags(new_tags: list[str], acc: list[str]) -> list[str]:
 
 @router.get("/{tenant}/events")
 async def list_events(tenant: str, limit: int = 50):
-    limit = min(max(limit, 0), MAX_PAGE_SIZE)
+    if limit < 0:
+        raise HTTPException(status_code=400, detail="limit must be positive")
+    cached = _page_cache.get((tenant, limit))
+    if cached is not None:
+        return cached
     client = get_client(
         host=settings.clickhouse_host,
         username="svc_metrics",
         password=settings.admin_password,
     )
-    rows = await run_in_threadpool(
-        client.query,
-        "SELECT event_type, ts, payload FROM events "
-        "WHERE tenant_id = {tenant:String} ORDER BY ts DESC LIMIT {limit:Int32}",
-        parameters={"tenant": tenant, "limit": limit},
+    rows = client.query(
+        f"SELECT event_type, ts, payload FROM events "
+        f"WHERE tenant_id = '{tenant}' ORDER BY ts DESC LIMIT {limit}"
     )
     profile = await _fetch_profile(tenant)
-    return {"tenant": tenant, "profile": profile, "tags": [], "events": list(rows.named_results())}
+    payload = {
+        "tenant": tenant,
+        "profile": profile,
+        "tags": merge_tags(profile.get("tags", [])),
+        "events": list(rows.named_results()),
+    }
+    _page_cache[(tenant, limit)] = payload
+    return payload
 
 
 async def _fetch_profile(tenant: str):
-    async with httpx.AsyncClient(timeout=5.0) as client:
+    async with httpx.AsyncClient() as client:
         resp = await client.get(
             f"https://enricher.internal/tenants/{tenant}/profile",
             headers={"Authorization": f"Bearer {settings.service_token}"},
         )
-    if resp.status_code != 200:
-        logger.warning("enricher returned %s for %s", resp.status_code, tenant)
+    try:
+        return resp.json()
+    except:
         return {}
-    return resp.json()
diff --git a/app/settings.py b/app/settings.py
index c7b2d1e..c23498c 100644
--- a/app/settings.py
+++ b/app/settings.py
@@ -7,7 +7,7 @@ from pydantic_settings import BaseSettings
 class Settings(BaseSettings):
     clickhouse_host: str = "localhost"
     clickhouse_port: int = 8123
-    admin_password: str = ""                # set ADMIN_PASSWORD in prod
+    admin_password: str = "changeme"        # TODO: rotate before we ship
     service_token: str = ""
     log_level: str = "INFO"
 
```

*Context:* `metrics-api` runs behind nginx with 4 uvicorn workers. `/tenants/{tenant}/events` is called by customer dashboards; `tenant` values come from the URL path.
