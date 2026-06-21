from __future__ import annotations

import json
import os
import time

from app.scheduler.redis_queue import dispatch_once


def main() -> None:
    interval = int(os.getenv("AI_COMPANY_OS_SCHEDULER_POLL_SECONDS", "5"))
    if interval < 1 or interval > 300:
        raise ValueError("AI_COMPANY_OS_SCHEDULER_POLL_SECONDS must be between 1 and 300")
    while True:
        try:
            print(json.dumps(dispatch_once(), sort_keys=True), flush=True)
        except Exception as exc:
            print(json.dumps({"scheduler_dispatch_error": str(exc)}, sort_keys=True), flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
