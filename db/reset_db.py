from db.session import engine
from db.models import Base

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

print("DB reset complete")
