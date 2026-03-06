"""Progress tracking for long-running operations"""
import threading
from datetime import datetime
from typing import Dict, Any

class ProgressTracker:
    """Thread-safe progress tracker for upload and analysis operations"""
    
    def __init__(self):
        self._progress = {}
        self._lock = threading.Lock()
    
    def start_task(self, task_id: str, total_steps: int = 100) -> None:
        """Initialize a new progress tracking task"""
        with self._lock:
            self._progress[task_id] = {
                'status': 'started',
                'progress': 0,
                'total': total_steps,
                'current_step': 'Başlatılıyor...',
                'details': [],
                'metrics': {
                    'total_functions': 0,
                    'completed_functions': 0,
                    'remaining_functions': 0,
                    'active_thread': None,
                    'estimated_remaining_seconds': None,
                },
                'started_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
    
    def update(self, task_id: str, progress: int = None, step: str = None, detail: str = None) -> None:
        """Update progress for a task"""
        with self._lock:
            if task_id not in self._progress:
                return
            
            if progress is not None:
                self._progress[task_id]['progress'] = progress
            
            if step is not None:
                self._progress[task_id]['current_step'] = step
            
            if detail is not None:
                self._progress[task_id]['details'].append({
                    'message': detail,
                    'timestamp': datetime.now().isoformat()
                })
            
            self._progress[task_id]['updated_at'] = datetime.now().isoformat()

    def set_metrics(self, task_id: str, **kwargs) -> None:
        """Set task metrics such as function counters and thread info."""
        with self._lock:
            if task_id not in self._progress:
                return

            metrics = self._progress[task_id].setdefault('metrics', {})
            for key, value in kwargs.items():
                metrics[key] = value

            # Keep derived metrics in sync
            total = metrics.get('total_functions') or 0
            completed = metrics.get('completed_functions') or 0
            remaining = max(total - completed, 0)
            metrics['remaining_functions'] = remaining

            # ETA estimation based on throughput so far
            if total > 0 and completed > 0:
                try:
                    started_at = datetime.fromisoformat(self._progress[task_id]['started_at'])
                    elapsed_seconds = max((datetime.now() - started_at).total_seconds(), 1)
                    rate = completed / elapsed_seconds
                    if rate > 0:
                        metrics['estimated_remaining_seconds'] = int(remaining / rate)
                    else:
                        metrics['estimated_remaining_seconds'] = None
                except Exception:
                    metrics['estimated_remaining_seconds'] = None
            else:
                metrics['estimated_remaining_seconds'] = None

            self._progress[task_id]['updated_at'] = datetime.now().isoformat()
    
    def complete(self, task_id: str, success: bool = True, message: str = None) -> None:
        """Mark task as completed"""
        with self._lock:
            if task_id not in self._progress:
                return
            
            self._progress[task_id]['status'] = 'completed' if success else 'failed'
            self._progress[task_id]['progress'] = 100
            self._progress[task_id]['current_step'] = message or ('Tamamlandı' if success else 'Hata')
            metrics = self._progress[task_id].setdefault('metrics', {})
            total = metrics.get('total_functions') or 0
            completed = metrics.get('completed_functions') or 0
            if success and total > 0 and completed < total:
                metrics['completed_functions'] = total
                metrics['remaining_functions'] = 0
            metrics['estimated_remaining_seconds'] = 0 if success else metrics.get('estimated_remaining_seconds')
            self._progress[task_id]['updated_at'] = datetime.now().isoformat()
    
    def get_progress(self, task_id: str) -> Dict[str, Any]:
        """Get current progress for a task"""
        with self._lock:
            return self._progress.get(task_id, None)
    
    def cleanup(self, task_id: str) -> None:
        """Remove completed task from tracker"""
        with self._lock:
            self._progress.pop(task_id, None)

# Global progress tracker instance
progress_tracker = ProgressTracker()
