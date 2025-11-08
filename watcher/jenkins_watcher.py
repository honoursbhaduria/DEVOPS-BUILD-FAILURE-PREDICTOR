import os
import time
import json
import logging
import jenkins
from sqlalchemy import create_engine, text
from config.settings import settings
from datetime import datetime
import hashlib
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jenkins-watcher")

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
server = jenkins.Jenkins(settings.JENKINS_URL, username=settings.JENKINS_USER, password=settings.JENKINS_TOKEN)

LAST_FILE = "data/last_checked.json"
os.makedirs("data/raw_logs", exist_ok=True)

def get_last_checked():
    if os.path.exists(LAST_FILE):
        return json.load(open(LAST_FILE))
    return {"last_build_number": 0}

def set_last_checked(data):
    json.dump(data, open(LAST_FILE, "w"))

def extract_error_count(raw_log: str) -> int:
    # naive heuristic: count occurrences of 'ERROR' or stack traces
    return len(re.findall(r"\bERROR\b", raw_log, flags=re.IGNORECASE))

def process_new_build(build_number):
    job = settings.JENKINS_JOB_NAME
    info = server.get_build_info(job, build_number)
    result = info.get("result")
    duration = info.get("duration")
    timestamp = info.get("timestamp")
    # try to collect commit message
    commit_message = ""
    actions = info.get("actions", [])
    for a in actions:
        if isinstance(a, dict) and "lastBuiltRevision" in a:
            commit_message = a.get("lastBuiltRevision", {}).get("branch", [{}])[0].get("SHA1", "")
    # get console log
    raw_log = server.get_build_console_output(job, build_number)
    error_count = extract_error_count(raw_log)
    # Save raw log file
    safe_name = f"{job}_{build_number}.log"
    raw_path = os.path.join("data/raw_logs", safe_name)
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(raw_log)

    # write to DB
    with engine.begin() as conn:
        insert_sql = text("""
        INSERT INTO builds (build_number, result, duration, timestamp, raw_log_path, raw_log, commit_message, error_count)
        VALUES (:build_number, :result, :duration, :timestamp, :raw_log_path, :raw_log, :commit_message, :error_count)
        ON CONFLICT (build_number) DO NOTHING
        """)
        conn.execute(insert_sql, {
            "build_number": build_number,
            "result": result,
            "duration": duration,
            "timestamp": datetime.fromtimestamp(timestamp/1000.0),
            "raw_log_path": raw_path,
            "raw_log": raw_log,
            "commit_message": commit_message,
            "error_count": error_count
        })
    logger.info("Saved build %s result=%s errors=%d", build_number, result, error_count)

def check_for_new_builds():
    job = settings.JENKINS_JOB_NAME
    info = server.get_job_info(job)
    builds = info.get("builds", [])
    if not builds:
        return []
    last_checked = get_last_checked()
    last_seen = int(last_checked.get("last_build_number", 0))
    new_builds = [b['number'] for b in builds if b['number'] > last_seen]
    new_builds = sorted(new_builds)
    for bnum in new_builds:
        try:
            process_new_build(bnum)
            last_seen = max(last_seen, bnum)
            set_last_checked({"last_build_number": last_seen})
        except Exception as e:
            logger.exception("Failed processing build %s: %s", bnum, e)

if __name__ == "__main__":
    logger.info("Watcher started. Polling every %d seconds", settings.CHECK_INTERVAL_SECONDS)
    while True:
        try:
            check_for_new_builds()
        except Exception as e:
            logger.exception("Watcher error: %s", e)
        time.sleep(settings.CHECK_INTERVAL_SECONDS)
