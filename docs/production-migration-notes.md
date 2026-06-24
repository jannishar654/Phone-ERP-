# Production Migration Notes

## Handling Legacy and Orphan Records

During the transition from `REQUIRE_AUTH=false` (demo/preview mode) to `REQUIRE_AUTH=true` (production-ready authenticated mode), it is expected that legacy records may lack a correct `user_id` or `shop_id`.

Please note the following behavior and rules for production:

1. **Legacy NULL Records:** Old records (Action Cards, Orders, Catalog Items) created before `REQUIRE_AUTH=true` was enforced may have `user_id` or `shop_id` set to `NULL` (or a hardcoded demo UUID).
2. **Shop Isolation & RLS Visibility:** Due to strict Row-Level Security (RLS) policies and shop isolation, these legacy or orphan records will **not** be visible to authenticated users in the application. This is the intended and secure behavior.
3. **New Records:** Any new records created after the fix will properly attach the real Supabase authenticated `user_id` and the corresponding `shop_id`.
4. **Production Strategy:** For the main deployed production flow, you have two options:
   - **Option A (Recommended):** Simply ignore demo/orphan records. Treat them as test artifacts and let authenticated users start fresh.
   - **Option B:** Run a manual, one-time SQL backfill script against the Supabase database to assign these orphan records to a specific, selected owner `user_id` or `shop_id`.
5. **No Automatic Backfills:** Do **not** execute any automatic backfills or merges of old NULL records into real user accounts unless explicitly requested and reviewed.
6. **Security Standard:** Do **not** weaken the Row-Level Security (RLS) policies for production just to make legacy records visible. The application must strictly enforce `REQUIRE_AUTH=true` rules.
