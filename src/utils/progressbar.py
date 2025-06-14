from tqdm import tqdm
import threading
import time

def progress_bar(total: int, desc: str, stop_event: threading.Event, lock: threading.Lock, fetched_blocks_ref: list):
    """
    Progress bar that increments for every block processed
    """
    progress_bar = tqdm(total=total, desc=desc, unit="block", ncols=100, leave=True)
    last_count = 0

    while not stop_event.is_set():
        try:
            with lock:
                current_count = fetched_blocks_ref[0]
            
            increment = current_count - last_count
            if increment > 0:
                progress_bar.update(increment)
                last_count = current_count
            
            time.sleep(0.1)
            
        except Exception:
            time.sleep(0.1)
            continue

    try:
        with lock:
            final_count = fetched_blocks_ref[0]
        
        if final_count > last_count:
            progress_bar.update(final_count - last_count)
    except:
        pass
    
    progress_bar.close()