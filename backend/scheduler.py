import time
import threading
import logging
from typing import Dict, Any, Optional

from schema import SearchFilter, ListingItem
from backend.db import (
    get_filters, get_filter, save_listings, record_scan_log,
    get_setting, set_setting, get_listings
)
from backend.scraper import scrape_marketplace_listings, is_cached_photo_valid
from backend.notifier import send_alert_email

logger = logging.getLogger(__name__)

def photo_capture_warning(items):
    missing = sum(not is_cached_photo_valid(item.listing_id) for item in items)
    return f"{missing} original photo(s) unavailable after capture and recovery." if missing else ""

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
                    cls._instance.last_scan_result = None
        return cls._instance

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_scanning": self.is_running,
            "status_message": self.status_message,
            "last_scan_time": self.last_scan_time,
            "last_scan_result": self.last_scan_result,
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
        f_data = None
        with self._lock:
            if self.is_running:
                logger.warning("Scan already in progress.")
                return
            self.is_running = True
            self.last_scan_result = None

        try:
            f_data = get_filter(filter_id)
            if not f_data:
                self.status_message = "Search rule not found."
                self.last_scan_result = {"status": "error", "message": self.status_message}
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
                count_new=new_count,
                error=photo_capture_warning(items)
            )

            if new_count > 0 and f.notify_email:
                recent_items = get_listings(filter_id=f.id, limit=new_count)
                alert_items = [ListingItem.from_dict(it) for it in recent_items if it.get("interest_status") == "interested" and not it.get("is_dismissed")]
                if alert_items:
                    send_alert_email(f, alert_items)

            self.status_message = f"Done! Found {len(items)} items ({new_count} new)."
            self.last_scan_result = {"status": "success", "count_found": len(items), "count_new": new_count}
            self.last_scan_time = time.time()
        except Exception as e:
            logger.error(f"Scan error for filter {filter_id}: {e}")
            err_str = str(e)
            status_lbl = "Needs Login" if ("login" in err_str.lower() or "session" in err_str.lower()) else "Error"
            self.status_message = "Scan failed: Facebook login required." if status_lbl == "Needs Login" else f"Error: {err_str}"
            self.last_scan_result = {"status": "error", "message": self.status_message}
            record_scan_log(
                filter_id=filter_id,
                filter_name=f_data.get("name", "Unknown") if f_data else "",
                status=status_lbl,
                count_found=0,
                count_new=0,
                error=err_str
            )
        finally:
            self.last_scan_time = time.time()
            self.is_running = False

    def _execute_all_scans(self):
        with self._lock:
            if self.is_running:
                logger.warning("Scan already in progress.")
                return
            self.is_running = True
            self.last_scan_result = None

        try:
            filters = get_filters()
            enabled_filters = [SearchFilter.from_dict(f) for f in filters if f.get("enabled")]

            if not enabled_filters:
                self.status_message = "No enabled filters to scan."
                self.last_scan_result = {"status": "error", "message": self.status_message}
                return

            total_found = 0
            total_new = 0
            failed_count = 0
            needs_login = False

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
                        count_new=new_count,
                        error=photo_capture_warning(items)
                    )

                    if new_count > 0 and f.notify_email:
                        recent_items = get_listings(filter_id=f.id, limit=new_count)
                        alert_items = [ListingItem.from_dict(it) for it in recent_items if it.get("interest_status") == "interested" and not it.get("is_dismissed")]
                        if alert_items:
                            send_alert_email(f, alert_items)

                except Exception as ex:
                    failed_count += 1
                    logger.error(f"Error scanning {f.name}: {ex}")
                    err_str = str(ex)
                    status_lbl = "Needs Login" if ("login" in err_str.lower() or "session" in err_str.lower()) else "Error"
                    record_scan_log(
                        filter_id=f.id,
                        filter_name=f.name,
                        status=status_lbl,
                        count_found=0,
                        count_new=0,
                        error=err_str
                    )
                    if status_lbl == "Needs Login":
                        needs_login = True
                        self.status_message = "Scan stopped: Facebook session required. Connect your account to enable scanning."
                        break

            if not needs_login:
                if failed_count:
                    self.status_message = f"Scan finished with {failed_count} failed filter(s). Found {total_found} listings ({total_new} new)."
                else:
                    self.status_message = f"Completed all scans. Found {total_found} listings ({total_new} new)."
            self.last_scan_time = time.time()
            self.last_scan_result = {
                "status": "error" if needs_login or failed_count else "success",
                "count_found": total_found,
                "count_new": total_new,
                "message": self.status_message
            }
        except Exception as error:
            logger.error("Scan failed: %s", error)
            self.status_message = f"Scan failed: {error}"
            self.last_scan_result = {"status": "error", "message": self.status_message}
        finally:
            self.last_scan_time = time.time()
            self.is_running = False

scan_manager = ScanManager()
