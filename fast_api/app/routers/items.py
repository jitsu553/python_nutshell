from fastapi import APIRouter, HTTPException

from app.db import create_item, delete_item, get_all_items, get_item_by_id, update_item
from app.schemas import Item

router = APIRouter(prefix="/items", tags=["items"])


@router.post("")
def create_item_route(item: Item):
    #print(item.model_dump())
    return create_item(item.model_dump())


@router.get("/{item_id}")
def get_item(item_id: int):
    stored_item = get_item_by_id(item_id)
    if stored_item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return stored_item


@router.get("")
def get_all_items_route():
    return get_all_items()


@router.put("/{item_id}")
def update_item_route(item_id: int, item: Item):
    updated_item = update_item(item_id, item.model_dump())
    if updated_item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return updated_item


@router.delete("/{item_id}")
def delete_item_route(item_id: int):
    was_deleted = delete_item(item_id)
    if not was_deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"item_id": item_id, "deleted": True}
