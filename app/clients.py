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

def ms2_list_items_by_user(uni: str):
    r = requests.get(f"{MS2}/items", params={"seller_uni": uni}, timeout=5)
    r.raise_for_status()
    return r.json()

def ms2_delete_items_by_user(uni: str):
    r = requests.delete(f"{MS2}/items", params={"seller_uni": uni}, timeout=15)
    return r.status_code
