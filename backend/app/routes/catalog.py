from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.dependencies.auth import get_current_user_id
from app.schemas.catalog import CatalogItemCreate, CatalogItemUpdate, CatalogItemResponse
from app.services.catalog_service import catalog_service
from app.services.supabase import supabase_client

router = APIRouter(prefix="/catalog", tags=["Catalog"])

def get_user_shop_id(user_id: str) -> str:
    from app.config.settings import settings
    
    if settings.REQUIRE_AUTH and not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    if supabase_client is None:
        return "mock-shop"
        
    if not settings.REQUIRE_AUTH and not user_id:
        # Demo mode: Use the shop where owner_id is NULL
        res = supabase_client.table("shops").select("id").is_("owner_id", "null").execute()
        if not res.data:
            try:
                shop_data = {
                    "name": "Demo Shop",
                    "phone": "+910000000000"
                }
                new_shop = supabase_client.table("shops").insert(shop_data).execute()
                if new_shop.data:
                    return new_shop.data[0]["id"]
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Demo shop creation failed: {e}")
            raise HTTPException(status_code=500, detail="Demo shop creation failed. Make sure to run the 005_demo_mode_support.sql migration.")
        return res.data[0]["id"]

    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    # Helper to get the first shop_id for the user
    res = supabase_client.table("shops").select("id").eq("owner_id", user_id).execute()
    if not res.data:
        # If no shop exists, let's create a default one to avoid unhandled exceptions
        try:
            shop_data = {
                "owner_id": user_id,
                "name": "Default Shop",
                "phone": "+910000000000"
            }
            new_shop = supabase_client.table("shops").insert(shop_data).execute()
            if new_shop.data:
                return new_shop.data[0]["id"]
        except Exception:
            pass
        raise HTTPException(status_code=404, detail="User has no shop and default shop creation failed")
    return res.data[0]["id"]

@router.post("/", response_model=CatalogItemResponse)
def create_catalog_item(item: CatalogItemCreate, user_id: str = Depends(get_current_user_id)):
    # Verify shop ownership
    shop_id = get_user_shop_id(user_id)
    if item.shop_id and item.shop_id != shop_id:
        raise HTTPException(status_code=403, detail="Not authorized to add items to this shop")
    item.shop_id = shop_id
    
    try:
        created = catalog_service.create_item(item)
        if not created:
            raise HTTPException(status_code=500, detail="Failed to create catalog item")
        return created
    except ValueError as e:
        if str(e) == "This catalog item already exists":
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[CatalogItemResponse])
def get_catalog_items(user_id: str = Depends(get_current_user_id)):
    shop_id = get_user_shop_id(user_id)
    items = catalog_service.get_items_by_shop(shop_id)
    return items

@router.put("/{item_id}", response_model=CatalogItemResponse)
def update_catalog_item(item_id: str, item: CatalogItemUpdate, user_id: str = Depends(get_current_user_id)):
    shop_id = get_user_shop_id(user_id)
    # RLS ensures they can only update their own shop's items, but we can just call the service.
    updated = catalog_service.update_item(item_id, item)
    if not updated:
        raise HTTPException(status_code=404, detail="Item not found or failed to update")
    return updated

@router.delete("/{item_id}")
def deactivate_catalog_item(item_id: str, user_id: str = Depends(get_current_user_id)):
    shop_id = get_user_shop_id(user_id)
    # Deactivate instead of delete
    updated = catalog_service.update_item(item_id, CatalogItemUpdate(active=False))
    if not updated:
        raise HTTPException(status_code=404, detail="Item not found or failed to deactivate")
    return {"message": "Item deactivated"}
