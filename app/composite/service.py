from concurrent.futures import ThreadPoolExecutor, as_completed
from app.clients import (
    ms1_get_user, ms1_delete_user,
    ms2_list_items_by_user_id, ms2_delete_items_by_user_id
)
import logging

logger = logging.getLogger(__name__)

pool = ThreadPoolExecutor(max_workers=4)

def delete_user_and_items(uni: str):
    """
    Composite service to delete user and all their items.
    
    Implements logical foreign key constraints:
    - Validates user exists in ms1 before attempting deletion
    - Only deletes items that belong to the user (seller_uni constraint)
    - Prevents deletion if user has active reservations/sales
    
    Uses parallel execution with threads for ms1 and ms2 deletion.
    """
    # Logical foreign key constraint: Check if user exists and get user_id
    user, _ = ms1_get_user(uni)
    if not user:
        return 404, {"error": "User not found", "uni": uni}
    
    # Get user_id from ms1 response (logical foreign key: seller_id references Users.user_id)
    user_id = user.get("user_id")
    if not user_id:
        return 500, {"error": "User data missing user_id", "uni": uni}
    
    logger.info(f"User {uni} has user_id: {user_id}")
    
    # Logical foreign key constraint: Get only items belonging to this user by seller_id
    try:
        items = ms2_list_items_by_user_id(user_id)
        # Ensure items is a list
        if not isinstance(items, list):
            items = []
        logger.info(f"Found {len(items)} items for user_id {user_id} (uni: {uni})")
    except Exception as e:
        # If ms2 is unavailable, we can't proceed safely
        logger.error(f"Error getting items from ms2: {e}")
        return 503, {"error": "Catalog service unavailable", "details": str(e)}
    
    # Logical foreign key constraint: Prevent deletion if items are in use
    blocked = []
    for item in items:
        item_id = item.get("item_id") or item.get("id")
        status = item.get("status")
        if status in {"reserved", "sold"}:
            blocked.append(item_id)
    
    if blocked:
        return 409, {
            "reason": "Active reservations/sales exist",
            "blocked_items": blocked,
            "message": "Cannot delete user with active reservations or sold items"
        }
    
    # Parallel execution: Delete from both services simultaneously using threads
    # Use user_id for ms2 (seller_id references Users.user_id)
    futures = {
        pool.submit(ms2_delete_items_by_user_id, user_id): "ms2_catalog",
        pool.submit(ms1_delete_user, uni): "ms1_identity",
    }
    
    result = {}
    errors = []
    
    for fut in as_completed(futures):
        service_name = futures[fut]
        try:
            response = fut.result()
            # ms1_delete_user returns (status_code, body) tuple
            # ms2_delete_items_by_user returns status_code (int)
            if service_name == "ms1_identity":
                status_code = response[0] if isinstance(response, tuple) else response
            else:  # ms2_catalog
                status_code = response
            
            if service_name == "ms2_catalog":
                if status_code in (200, 204):
                    result[service_name] = "deleted"
                elif status_code == 404:
                    result[service_name] = "none"  # No items to delete
                else:
                    result[service_name] = f"failed:{status_code}"
                    errors.append(f"{service_name} returned {status_code}")
            else:  # ms1_identity
                if status_code == 200:
                    result[service_name] = "deleted"
                elif status_code == 404:
                    result[service_name] = "not_found"
                else:
                    result[service_name] = f"failed:{status_code}"
                    errors.append(f"{service_name} returned {status_code}")
        except Exception as e:
            result[service_name] = f"error:{str(e)}"
            errors.append(f"{service_name} error: {str(e)}")
    
    # Determine response based on results
    ms1_status = result.get("ms1_identity", "unknown")
    ms2_status = result.get("ms2_catalog", "unknown")
    
    if ms1_status == "deleted" and ms2_status in ("deleted", "none"):
        return 200, {
            "ms1_identity": "deleted",
            "ms2_catalog": "deleted" if ms2_status == "deleted" else "none",
            "message": "User and all items deleted successfully"
        }
    
    # Partial success or failure
    response_body = {
        "ms1_identity": ms1_status,
        "ms2_catalog": ms2_status
    }
    if errors:
        response_body["errors"] = errors
    
    return 207, response_body
