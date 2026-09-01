from app.db.client import get_supabase_client

DEV_PLACEHOLDER_USER_ID = "9b14eeaf-59ab-44a0-8c97-ef3cfeb8f1d6"

client = get_supabase_client()

analysis_response = (
    client.table("analysis_results")
    .delete()
    .eq("user_id", DEV_PLACEHOLDER_USER_ID)
    .execute()
)
print("Deleted analysis_results rows:", len(analysis_response.data))

models_response = (
    client.table("registered_models")
    .delete()
    .eq("user_id", DEV_PLACEHOLDER_USER_ID)
    .execute()
)
print("Deleted registered_models rows:", len(models_response.data))