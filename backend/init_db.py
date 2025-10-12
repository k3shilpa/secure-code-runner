from database import engine, Base
from models import CodeSnippet

Base.metadata.create_all(bind=engine)
print("✅ Fresh database created!")
