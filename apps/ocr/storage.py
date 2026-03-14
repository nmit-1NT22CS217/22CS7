"""
Storage module for managing encrypted PII mappings with TTL-based auto-expiry.
Handles reading/writing encrypted mapping files with time-limited persistence
to minimize breach exposure risk.
"""
import json
import os
import time
import threading
from typing import Dict, Optional
try:
    from .crypto_util import encrypt_data, decrypt_data
except ImportError:  # Support running as a top-level module (e.g., Railway root=apps/ocr)
    from crypto_util import encrypt_data, decrypt_data

# Default TTL: 30 minutes (1800 seconds)
DEFAULT_MAPPING_TTL = 30 * 60
# Minimum allowed TTL: 1 minute
MIN_TTL = 60
# Maximum allowed TTL: 24 hours
MAX_TTL = 24 * 60 * 60
# Cleanup interval: check every 60 seconds
CLEANUP_INTERVAL = 60


class MappingStorage:
    """
    Manages encrypted storage of PII mappings with automatic time-based expiry.
    
    Security features:
    - All mappings are encrypted at rest using Fernet (AES-128-CBC)
    - Each mapping entry has a timestamp; expired entries are purged automatically
    - A background cleanup thread removes stale mappings periodically
    - TTL is configurable (default 30 min, range 1 min – 24 hours)
    - Mappings can be cleared instantly via clear_mappings()
    """
    
    def __init__(self, filepath: str, encryption_key: bytes,
                 ttl_seconds: int = DEFAULT_MAPPING_TTL,
                 auto_cleanup: bool = True):
        """
        Initialize the mapping storage.
        
        Args:
            filepath: Path to the encrypted mappings file
            encryption_key: Fernet encryption key
            ttl_seconds: Time-to-live for each mapping entry in seconds (default: 1800 = 30 min)
            auto_cleanup: Whether to run a background thread that purges expired entries
        """
        self.filepath = filepath
        self.encryption_key = encryption_key
        self.ttl_seconds = max(MIN_TTL, min(MAX_TTL, ttl_seconds))
        self._lock = threading.Lock()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._running = False
        
        if auto_cleanup:
            self._start_cleanup_thread()
    
    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    
    def save_mappings(self, mappings: Dict[str, str]) -> None:
        """
        Save PII mappings to encrypted file (raw, without timestamps).
        Kept for backward compatibility — prefer add_mappings() for TTL support.
        """
        with self._lock:
            self._write_store(self._wrap_entries(mappings))
    
    def load_mappings(self) -> Dict[str, str]:
        """
        Load non-expired PII mappings from encrypted file.
        
        Returns:
            Dictionary of placeholder -> original PII value (expired entries excluded)
        """
        with self._lock:
            store = self._read_store()
            now = time.time()
            active = {}
            for key, entry in store.items():
                if self._is_valid(entry, now):
                    active[key] = entry['value']
            return active
    
    def add_mappings(self, new_mappings: Dict[str, str]) -> None:
        """
        Add new mappings to existing ones, each stamped with the current time.
        Expired entries are pruned during this operation.
        """
        with self._lock:
            store = self._read_store()
            now = time.time()
            # Prune expired
            store = {k: v for k, v in store.items() if self._is_valid(v, now)}
            # Add new with timestamp
            for key, value in new_mappings.items():
                store[key] = {'value': value, 'ts': now}
            self._write_store(store)
    
    def clear_mappings(self) -> None:
        """Securely clear all stored mappings immediately."""
        with self._lock:
            if os.path.exists(self.filepath):
                # Overwrite with empty data before deleting (defense in depth)
                try:
                    with open(self.filepath, 'wb') as f:
                        f.write(b'\x00' * 64)
                        f.flush()
                        os.fsync(f.fileno())
                except Exception:
                    pass
                os.remove(self.filepath)
    
    def get_mapping_count(self) -> int:
        """Return the number of active (non-expired) mappings."""
        return len(self.load_mappings())
    
    def get_ttl_seconds(self) -> int:
        """Return the current TTL setting in seconds."""
        return self.ttl_seconds
    
    def set_ttl_seconds(self, ttl: int) -> None:
        """Update the TTL (clamped to MIN_TTL..MAX_TTL)."""
        self.ttl_seconds = max(MIN_TTL, min(MAX_TTL, ttl))
    
    def get_storage_info(self) -> Dict:
        """Return a summary of storage state (for health/debug endpoints)."""
        with self._lock:
            store = self._read_store()
            now = time.time()
            total = len(store)
            active = sum(1 for v in store.values() if self._is_valid(v, now))
            expired = total - active
            oldest_age = 0
            if store:
                oldest_ts = min(
                    (v.get('ts', 0) for v in store.values()),
                    default=now
                )
                oldest_age = round(now - oldest_ts)
            return {
                'total_entries': total,
                'active_entries': active,
                'expired_entries': expired,
                'ttl_seconds': self.ttl_seconds,
                'ttl_display': self._format_ttl(self.ttl_seconds),
                'oldest_entry_age_seconds': oldest_age,
                'auto_cleanup_active': self._running,
                'file_exists': os.path.exists(self.filepath),
            }
    
    def shutdown(self) -> None:
        """Stop the background cleanup thread."""
        self._running = False
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
    
    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    
    def _is_valid(self, entry: dict, now: float) -> bool:
        """Check if a mapping entry is still within its TTL."""
        if not isinstance(entry, dict) or 'ts' not in entry:
            return True  # Legacy entry without timestamp — treat as valid
        return (now - entry['ts']) < self.ttl_seconds
    
    def _wrap_entries(self, mappings: Dict[str, str]) -> Dict[str, dict]:
        """Wrap plain mappings with timestamps."""
        now = time.time()
        return {k: {'value': v, 'ts': now} for k, v in mappings.items()}
    
    def _read_store(self) -> Dict[str, dict]:
        """Read the raw store from disk (caller must hold _lock)."""
        if not os.path.exists(self.filepath):
            return {}
        try:
            with open(self.filepath, 'rb') as f:
                encrypted_data = f.read()
            json_data = decrypt_data(encrypted_data, self.encryption_key)
            raw = json.loads(json_data)
            # Support legacy format: plain {key: value_str}
            store = {}
            for k, v in raw.items():
                if isinstance(v, dict) and 'value' in v:
                    store[k] = v
                else:
                    # Legacy entry — wrap it with current time
                    store[k] = {'value': v, 'ts': time.time()}
            return store
        except Exception as e:
            print(f"Error loading mappings: {e}")
            return {}
    
    def _write_store(self, store: Dict[str, dict]) -> None:
        """Write the raw store to disk (caller must hold _lock)."""
        json_data = json.dumps(store, indent=2)
        encrypted_data = encrypt_data(json_data, self.encryption_key)
        with open(self.filepath, 'wb') as f:
            f.write(encrypted_data)
    
    def _cleanup_expired(self) -> int:
        """Purge expired entries from the store. Returns count of purged entries."""
        with self._lock:
            store = self._read_store()
            if not store:
                return 0
            now = time.time()
            before = len(store)
            store = {k: v for k, v in store.items() if self._is_valid(v, now)}
            after = len(store)
            purged = before - after
            if purged > 0:
                if store:
                    self._write_store(store)
                else:
                    # All entries expired — remove the file entirely
                    if os.path.exists(self.filepath):
                        os.remove(self.filepath)
                print(f"[MappingStorage] Purged {purged} expired mapping(s), {after} active")
            return purged
    
    def _start_cleanup_thread(self) -> None:
        """Start a daemon thread that periodically purges expired entries."""
        self._running = True
        
        def _worker():
            while self._running:
                try:
                    self._cleanup_expired()
                except Exception as e:
                    print(f"[MappingStorage] Cleanup error: {e}")
                # Sleep in small increments so shutdown is responsive
                for _ in range(CLEANUP_INTERVAL):
                    if not self._running:
                        break
                    time.sleep(1)
        
        self._cleanup_thread = threading.Thread(target=_worker, name='mapping-cleanup', daemon=True)
        self._cleanup_thread.start()
    
    @staticmethod
    def _format_ttl(seconds: int) -> str:
        """Format TTL seconds into a human-readable string."""
        if seconds < 120:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m"
        else:
            h = seconds // 3600
            m = (seconds % 3600) // 60
            return f"{h}h {m}m" if m else f"{h}h"
