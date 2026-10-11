import time
import threading
import logging
from typing import Dict, Any, Optional

from schema import SearchFilter
from backend.db import (
    get_filters, get_filter, save_listings, record_scan_log,
    get_setting, set_setting
)
from backend.scraper import scrape_marketplace_listings
from backend.notifier import send_alert_email

logger = logging.getLogger(__name__)

class ScanManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ScanManager, cls).__new__(cls)
                    cls._instance.is_running = False
                    cls._instance.status_message = "Idle"
                    cls._instance.worker_thread = None
                    cls._instance.stop_event = threading.Event()
                    cls._instance.last_scan_time = 0
        return cls._instance

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_scanning": self.is_running,
            "status_message": self.status_message,
            "last_scan_time": self.last_scan_time,
            "auto_scan_enabled": get_setting("auto_scan_enabled", "1") == "1",
            "scan_interval_minutes": int(get_setting("scan_interval_minutes", "60"))
        }

    def start_background_scheduler(self):
        if self.worker_thread is not None and self.worker_thread.is_alive():
            return
        self.stop_event.clear()
        self.worker_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.worker_thread.start()

    def _scheduler_loop(self):
        while not self.stop_event.is_set():
            try:
                auto_enabled = get_setting("auto_scan_enabled", "1") == "1"
                interval_min = int(get_setting("scan_interval_minutes", "60"))
                interval_sec = max(interval_min * 60, 300) # Minimum 5 minutes

                if auto_enabled and not self.is_running:
                    elapsed = time.time() - self.last_scan_time
                    if elapsed >= interval_sec:
                        self.run_scan_all()
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")

            time.sleep(30)

    def run_scan_for_filter(self, filter_id: int):
        t = threading.Thread(target=self._execute_filter_scan, args=(filter_id,))
        t.start()
        return t

    def run_scan_all(self):
        t = threading.Thread(target=self._execute_all_scans)
        t.start()
        return t

    def _execute_filter_scan(self, filter_id: int):
        with self._lock:
            if self.is_running:
                logger.warning("Scan already in progress.")
                return
            self.is_running = True

        try:
            f_data = get_filter(filter_id)
            if not f_data:
                return
            f = SearchFilter.from_dict(f_data)
            self.status_message = f"Scanning '{f.name}'..."
            
            items = scrape_marketplace_listings(f)
            new_count = save_listings(items)
            
            record_scan_log(
                filter_id=f.id,
                filter_name=f.name,
                status="Success",
                count_found=len(items),
                count_new=new_count
            )

            if new_count > 0 and f.notify_email:
                new_items = items[:new_count]
                send_alert_email(f, new_items)

            self.status_message = f"Done! Found {len(items)} items ({new_count} new)."
            self.last_scan_time = time.time()
        except Exception as e:
            logger.error(f"Scan error for filter {filter_id}: {e}")
            self.status_message = f"Error: {str(e)}"
            record_scan_log(
                filter_id=filter_id,
                filter_name=f_data.get("name", "Unknown") if f_data else "",
                status="Error",
                count_found=0,
                count_new=0,
                error=str(e)
            )
        finally:
            self.is_running = False

    def _execute_all_scans(self):
        with self._lock:
            if self.is_running:
                logger.warning("Scan already in progress.")
                return
            self.is_running = True

        try:
            filters = get_filters()
            enabled_filters = [SearchFilter.from_dict(f) for f in filters if f.get("enabled")]

            if not enabled_filters:
                self.status_message = "No enabled filters to scan."
                return

            total_found = 0
            total_new = 0

            for idx, f in enumerate(enabled_filters):
                self.status_message = f"Scanning filter {idx+1}/{len(enabled_filters)}: '{f.name}'..."
                try:
                    items = scrape_marketplace_listings(f)
                    new_count = save_listings(items)
                    total_found += len(items)
                    total_new += new_count

                    record_scan_log(
                        filter_id=f.id,
                        filter_name=f.name,
                        status="Success",
                        count_found=len(items),
                        count_new=new_count
                    )

                    if new_count > 0 and f.notify_email:
                        new_items = items[:new_count]
                        send_alert_email(f, new_items)

                except Exception as ex:
                    logger.error(f"Error scanning {f.name}: {ex}")
                    record_scan_log(
                        filter_id=f.id,
                        filter_name=f.name,
                        status="Error",
                        count_found=0,
                        count_new=0,
                        error=str(ex)
                    )

            self.status_message = f"Completed all scans. Found {total_found} listings ({total_new} new)."
            self.last_scan_time = time.time()
        finally:
            self.is_running = False

scan_manager = ScanManager()
