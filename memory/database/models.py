import uuid

from sqlalchemy import TIMESTAMP, Column, Integer, String, Text, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()
metadata = Base.metadata


class DataSource(Base):
    __tablename__ = "gpt4people_data_sources"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    app_id = Column(Text, index=True)
    hash = Column(Text, index=True)
    type = Column(Text, index=True)
    value = Column(Text)
    meta_data = Column(Text, name="metadata")
    is_uploaded = Column(Integer, default=0)


class ChatHistoryModel(Base):
    __tablename__ = "gpt4people_chat_history"

    app_id = Column(String, primary_key=True)
    id = Column(String, primary_key=True)
    user_name = Column(String, primary_key=True, index=True)
    user_id = Column(String, primary_key=True, index=True)
    session_id = Column(String, primary_key=True, index=True)
    question = Column(Text)
    answer = Column(Text)
    meta_data = Column(Text, name="metadata")
    created_at = Column(TIMESTAMP, default=func.current_timestamp(), index=True)
    
    
class ChatHistoryByRoleModel(Base):
    __tablename__ = "gpt4people_chat_history_by_role"
    id = Column(String, primary_key=True) 
    sender_name = Column(String, primary_key=True, index=True)
    responder_name = Column(String, primary_key=True, index=True)
    sender_text = Column(Text)
    responder_text = Column(Text)
    created_at = Column(TIMESTAMP, default=func.current_timestamp(), index=True)


class ChatSessionModel(Base):
    __tablename__ = "gpt4people_session_history"

    app_id = Column(String, primary_key=True)
    id = Column(String, primary_key=True)
    user_name = Column(String, primary_key=True, index=True)
    user_id = Column(String, primary_key=True, index=True)
    session_id = Column(String, primary_key=True, index=True)
    meta_data = Column(Text, name="metadata")
    created_at = Column(TIMESTAMP, default=func.current_timestamp(), index=True)


class MemoryRunModel(Base):
    __tablename__ = "gpt4people_run_history"

    agent_id = Column(String, primary_key=True)
    id = Column(String, primary_key=True)
    user_name = Column(String, primary_key=True, index=True)
    user_id = Column(String, primary_key=True, index=True)
    run_id = Column(String, primary_key=True, index=True)
    meta_data = Column(Text, name="metadata")
    created_at = Column(TIMESTAMP, default=func.current_timestamp(), index=True)
