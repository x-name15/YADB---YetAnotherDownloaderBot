import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import json

async def test_connection():
    try:

        print("Intentando conectar a MongoDB...")
        client = AsyncIOMotorClient("mongodb://mongo:27017/", serverSelectionTimeoutMS=5000)

        await client.admin.command('ping')
        print("✅ Conexión a MongoDB exitosa")

        db = client["mediadownloader"]
        print(f"Creando documento de prueba en la base de datos 'mediadownloader'")
        result = await db.test_collection.insert_one({
            "test": True,
            "message": "Documento de prueba",
            "timestamp": asyncio.get_event_loop().time()
        })
        print(f"✅ Documento creado con ID: {result.inserted_id}")

        db_list = await client.list_database_names()
        print(f"Bases de datos disponibles: {db_list}")

        collections = await db.list_collection_names()
        print(f"Colecciones en 'mediadownloader': {collections}")

        count = await db.test_collection.count_documents({})
        print(f"Documentos en 'test_collection': {count}")
        
        print("\n¡Todo funciona correctamente!")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())