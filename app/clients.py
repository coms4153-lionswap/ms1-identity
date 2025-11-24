# app/clients.py
import os
import requests

# Read from environment variables
MS1 = os.getenv("MS1_BASE", "http://localhost:8000")
MS2 = os.getenv("MS2_BASE", "http://localhost:8080")

def ms1_get_user(uni: str):
    r = requests.get(f"{MS1}/users/{uni}", timeout=5)
    if r.status_code == 404:
        return None, None
    r.raise_for_status()
    return r.json(), r.headers.get("ETag")

def ms1_delete_user(uni: str):
    r = requests.delete(f"{MS1}/users/{uni}", timeout=5)
    return r.status_code, (r.json() if r.content else None)

def ms2_list_items_by_user_id(user_id: int):
    """
    Get all items from ms2 filtered by seller_id (logical foreign key constraint)
    seller_id references Users.user_id in ms2's Items table
    """
    try:
        # Try with seller_id parameter first
        r = requests.get(f"{MS2}/items", params={"seller_id": user_id}, timeout=5)
        r.raise_for_status()
        items = r.json()
        # If response is a list, filter by seller_id
        if isinstance(items, list):
            return [item for item in items if item.get("seller_id") == user_id]
        # If response is a dict with items key
        if isinstance(items, dict) and "items" in items:
            all_items = items["items"]
            return [item for item in all_items if item.get("seller_id") == user_id]
        return items if isinstance(items, list) else []
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return []  # No items found
        # If seller_id parameter doesn't work, try getting all items and filter
        try:
            r = requests.get(f"{MS2}/items", timeout=5)
            r.raise_for_status()
            all_items = r.json()
            # Filter by seller_id in memory (logical foreign key constraint)
            if isinstance(all_items, list):
                return [item for item in all_items if item.get("seller_id") == user_id]
            if isinstance(all_items, dict) and "items" in all_items:
                return [item for item in all_items["items"] if item.get("seller_id") == user_id]
            return []
        except Exception as e2:
            # If we can't get items, return empty list
            return []

def ms2_delete_item(item_id: str):
    """Delete a single item from ms2"""
    r = requests.delete(f"{MS2}/items/{item_id}", timeout=5)
    return r.status_code

def ms2_delete_items_by_user_id(user_id: int):
    """
    Delete all items belonging to a user from ms2 by seller_id.
    First gets the items, then deletes each one individually.
    Uses seller_id (logical foreign key: seller_id references Users.user_id)
    """
    try:
        # Get all items for this user by seller_id
        items = ms2_list_items_by_user_id(user_id)
        
        if not items or len(items) == 0:
            return 404  # No items to delete
        
        # Delete each item individually using threads for parallel execution
        from concurrent.futures import ThreadPoolExecutor, as_completed
        pool = ThreadPoolExecutor(max_workers=4)
        
        futures = []
        for item in items:
            item_id = item.get("item_id") or item.get("id")
            if item_id:
                futures.append(pool.submit(ms2_delete_item, str(item_id)))
        
        deleted_count = 0
        failed_count = 0
        
        for fut in as_completed(futures):
            try:
                status = fut.result()
                if status in (200, 204):
                    deleted_count += 1
                else:
                    failed_count += 1
            except:
                failed_count += 1
        
        if deleted_count == len(items):
            return 200  # All items deleted
        elif deleted_count > 0:
            return 207  # Partial success
        else:
            return 500  # Failed to delete any items
    except Exception as e:
        # If we can't get items, assume there are none
        return 404
