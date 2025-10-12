from sqlalchemy import Column, Integer, String, Text
from database import Base

class CodeSnippet(Base):
    __tablename__ = "code_history"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)      # Must exist
    language = Column(String, nullable=False)
    code = Column(Text, nullable=False)
    stdout = Column(Text, default="")
    stderr = Column(Text, default="")
    ai_explanation = Column(Text, default="")
    ai_fixed_code = Column(Text, default="")
