from concurrent.futures import ThreadPoolExecutor, as_completed
from app.clients import (
    ms1_get_user, ms1_delete_user,
    ms2_list_items_by_user, ms2_delete_items_by_user
)

pool = ThreadPoolExecutor(max_workers=4)

def delete_user_and_items(uni: str):
    user, _ = ms1_get_user(uni)
    if not user:
        return 404, {"error": "User not found"}

    items = ms2_list_items_by_user(uni)
    blocked = [i["item_id"] for i in items if i.get("status") in {"reserved", "sold"}]
    if blocked:
        return 409, {"reason": "Active reservations/sales exist", "blocked_items": blocked}

    futures = {
        pool.submit(ms2_delete_items_by_user, uni): "ms2",
        pool.submit(ms1_delete_user, uni): "ms1",
    }
    result = {}
    for fut in as_completed(futures):
        name = futures[fut]
        try:
            result[name] = fut.result()
        except Exception as e:
            result[name] = f"error:{e}"

    if result.get("ms1") in (200,) and result.get("ms2") in (200, 204, 404):
        return 200, {"ms1_identity": "deleted", "ms2_catalog": "deleted"}

    return 207, {"ms1_identity": result.get("ms1"), "ms2_catalog": result.get("ms2")}
