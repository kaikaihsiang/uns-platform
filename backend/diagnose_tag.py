import asyncio

from app.core.config import settings
from app.models import NamespaceNode, Tag, TagSourceMapping, UnsPayloadSchema
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Manual Engine Setup for script
engine = create_async_engine(settings.database_url)
async_session_local = async_sessionmaker(engine, expire_on_commit=False)

async def diagnose_tag_7():
    async with async_session_local() as db:
        # 1. Check Tag table
        tag_res = await db.execute(select(Tag).where(Tag.tag_id == 7))
        tag = tag_res.scalar_one_or_none()
        if not tag:
            print("Tag 7 not found in Tag table.")
            return
        
        print("--- Tag Table Info (ID: 7) ---")
        print(f"Display Name: {tag.display_name}")
        print(f"Data Point: {tag.data_point}")
        print(f"Category: {tag.category}")
        print(f"Default Unit: {tag.unit}")
        
        # 2. Check Mapping
        map_res = await db.execute(select(TagSourceMapping).where(TagSourceMapping.tag_id == 7))
        mapping = map_res.scalar_one_or_none()
        if not mapping:
            print("\n[!] No TagSourceMapping found for Tag 7.")
            return
        
        print("\n--- Mapping Info ---")
        print(f"MQTT Topic: {mapping.mqtt_topic}")
        
        # 3. Check Node & Schema
        node_res = await db.execute(select(NamespaceNode).where(NamespaceNode.full_path == mapping.mqtt_topic))
        node = node_res.scalar_one_or_none()
        if not node:
            print("\n[!] No NamespaceNode found for this Topic.")
            return
        
        if not node.schema_id:
            print("\n[!] Node found but no Schema assigned.")
            return
            
        schema_res = await db.execute(select(UnsPayloadSchema).where(UnsPayloadSchema.schema_id == node.schema_id))
        schema = schema_res.scalar_one_or_none()
        
        if not schema:
            print(f"\n[!] Schema ID {node.schema_id} points to nothing.")
            return

        print(f"\n--- Schema Info (ID: {node.schema_id}) ---")
        print(f"Schema Name: {schema.schema_name}")
        print(f"Fields Definition: {schema.fields}")
        
        # 4. Check if Data Point matches any field
        match = next((f for f in schema.fields if f.get("name") == tag.data_point), None)
        if match:
            print(f"\n[OK] Found matching field in schema: {match}")
        else:
            print(f"\n[!] DATA POINT MISMATCH: '{tag.data_point}' not found in schema fields.")
            print(f"Available fields: {[f.get('name') for f in schema.fields]}")

if __name__ == "__main__":
    asyncio.run(diagnose_tag_7())
