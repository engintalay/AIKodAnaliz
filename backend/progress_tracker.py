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
    
    def complete(self, task_id: str, success: bool = True, message: str = None) -> None:
        """Mark task as completed"""
        with self._lock:
            if task_id not in self._progress:
                return
            
            self._progress[task_id]['status'] = 'completed' if success else 'failed'
            self._progress[task_id]['progress'] = 100
            self._progress[task_id]['current_step'] = message or ('Tamamlandı' if success else 'Hata')
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
