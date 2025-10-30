import asyncio
from sqlalchemy import cast, select
from db import schemas
from db.database import *

from db import models

async def startup():
    await init_db_and_session(create_tables=True)
    
    db_gen = get_async_db()
    db : AsyncSession = await db_gen.__anext__()
    
    truck = {
        "id" : 1,
        "owner_user_id" : 23,
        "name" : "truck kun",
        "is_active" : True,
        "movement_status": "serving",
        "menu_json" :  {
           "8456a7ba-536f-4c72-976a-e8c485182b13": {
               "item_id": "8456a7ba-536f-4c72-976a-e8c485182b13", "name": "sushi", "description": "sushi with wasabi", "price": 12.1, "image_url": None
               },
           "fc7d23bc-e97c-43d1-a588-10ec693cbf34": {
               "item_id": "fc7d23bc-e97c-43d1-a588-10ec693cbf34", "name": "ramen", "description": "meso ramen", "price": 11.1, "image_url": None
               }, 
           "582111f0-c726-48de-bfc9-718b31917009": {
               "item_id": "582111f0-c726-48de-bfc9-718b31917009", "name": "lemon rice", "description": "indian lemo rice", "price": 7, "image_url": None
               }
        }
    }
    
    stmt = select(models.Truck).where(models.Truck.id == truck["id"])
        
    current_truck = (await db.execute(stmt)).scalars().all()

    print(type(current_truck[0].menu_json))

if __name__ == "__main__":
    
    asyncio.run(startup())