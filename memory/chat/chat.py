from datetime import datetime
import json
from loguru import logger
from pathlib import Path
import sys
import uuid
from typing import Any, Optional
from sqlalchemy import or_

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from memory.database.models import ChatHistoryModel, ChatSessionModel, MemoryRunModel, ChatHistoryByRoleModel
from chat.message import ChatMessage
from chat.utils import merge_metadata_dict
from loguru import logger
from memory.database.database import DatabaseManager


class ChatHistory:
    def __init__(self) -> None:
        self.db_session = DatabaseManager().get_session()

    def add(self, chat_message: ChatMessage, 
            app_id: Optional[str] = None,
            user_name: Optional[str] = None, 
            user_id: Optional[str] = None, 
            session_id: Optional[str] = None, 
            memory_id: Optional[str] = None,
            ) -> Optional[str]:
        
        if not any([app_id, user_name, user_id, session_id]):
            raise ValueError("One of app_id, user_name, user_id, session_id must be provided")
        
        if memory_id == None:
            memory_id = str(uuid.uuid4())

        metadata_dict = merge_metadata_dict(chat_message.human_message.metadata, chat_message.ai_message.metadata)
        if metadata_dict:
            metadata = self._serialize_json(metadata_dict)
        self.db_session.add(
            ChatHistoryModel(
                app_id=app_id,
                id=memory_id,
                user_name=user_name,
                user_id=user_id,
                session_id=session_id,
                question=chat_message.human_message.content,
                answer=chat_message.ai_message.content,
                metadata=metadata if metadata_dict else "{}",
            )
        )
        try:
            self.db_session.commit()
        except Exception as e:
            logger.error(f"Error adding chat memory to db: {e}")
            self.db_session.rollback()
            return None

        logger.debug(f"Added chat history to db with id: {memory_id}, app_id: {app_id}, user_name: {user_name}, user_id: {user_id}, session_id: {session_id}")
        return memory_id
    

    def add_by_role(self, sender_name: str, responder_name: str, sender_text: str, responder_text: str) -> Optional[str]:
        if not any([sender_name, responder_name]):
            raise ValueError("Both sender_name and responder_name must be provided")
        
        memory_id = str(uuid.uuid4())
        
        self.db_session.add(
            ChatHistoryByRoleModel(
                id=memory_id,
                sender_name=sender_name,
                responder_name=responder_name,
                sender_text=sender_text,
                responder_text=responder_text
            )
        )
        try:
            self.db_session.commit()
        except Exception as e:
            logger.error(f"Error adding chat history by role to db: {e}")
            self.db_session.rollback()
            return None

        logger.debug(f"Added chat history by role to db with id: {memory_id}, sender_name: {sender_name}, responder_name: {responder_name}")
        return memory_id
    

    def delete_by_role(self, sender_name: Optional[str] = None, responder_name: Optional[str] = None):
        """
        Delete chat history based on sender_name and/or responder_name.

        :param sender_name: The sender's name to delete chat history for
        :param responder_name: The responder's name to delete chat history for

        :return: None
        """
        logger.debug(f"Deleting chat history for sender_name: {sender_name}, responder_name: {responder_name}")
        params = {}
        if sender_name:
            params["sender_name"] = sender_name
        if responder_name:
            params["responder_name"] = responder_name
        if params:
            self.db_session.query(ChatHistoryByRoleModel).filter_by(**params).delete()
        else:
            raise ValueError("At least one of sender_name or responder_name must be provided to delete chat history by role")

        try:
            self.db_session.commit()
        except Exception as e:
            logger.error(f"Error deleting chat history by role: {e}")
            self.db_session.rollback()


    def get_hist_by_role(self, sender_name: Optional[str] = None, responder_name: Optional[str] = None, num_rounds: int = 10, fetch_all: bool = False, desc: bool = True) -> list:
        """
        Get the chat history based on sender_name and/or responder_name.

        :param sender_name: The sender's name to get chat history for
        :param responder_name: The responder's name to get chat history for
        :param num_rounds: The number of rounds to get chat history. Defaults to 10
        :param fetch_all: Whether to fetch all chat history or not. Defaults to False

        :return: List of chat history by role
        """
        if not sender_name or not responder_name:
            raise ValueError("Both sender_name and responder_name must be provided to get chat history by role")
        results = ()
        if desc == True:
            results = (
                self.db_session.query(ChatHistoryByRoleModel)
                .filter(
                    or_(
                        (ChatHistoryByRoleModel.sender_name == sender_name) & (ChatHistoryByRoleModel.responder_name == responder_name),
                        (ChatHistoryByRoleModel.sender_name == responder_name) & (ChatHistoryByRoleModel.responder_name == sender_name),
                    )
                )
                .order_by(ChatHistoryByRoleModel.created_at.desc())
            )
        else:
            results = (
                self.db_session.query(ChatHistoryByRoleModel)
                .filter(
                    or_(
                        (ChatHistoryByRoleModel.sender_name == sender_name) & (ChatHistoryByRoleModel.responder_name == responder_name),
                        (ChatHistoryByRoleModel.sender_name == responder_name) & (ChatHistoryByRoleModel.responder_name == sender_name),
                    )
                )
                .order_by(ChatHistoryByRoleModel.created_at.asc())
            )

        results = results.limit(num_rounds) if not fetch_all else results
        history = []
        for result in results:
            history.append(
                {
                    "id": result.id,
                    "sender_name": result.sender_name,
                    "responder_name": result.responder_name,
                    "sender_text": result.sender_text,
                    "responder_text": result.responder_text,
                    "created_at": result.created_at,
                }
            )
        if desc:
            history.reverse()
        return history

    def add_session(self,
            app_id: Optional[str] = None,
            user_name: Optional[str] = None, 
            user_id: Optional[str] = None, 
            session_id: Optional[str] = None, 
            memory_id: Optional[str] = None,
            created_at: Optional[datetime] = None,
            ) -> Optional[str]:
        
        if not any([app_id, user_name, user_id, session_id]):
            raise ValueError("One of app_id, user_id, session_id must be provided")
        
        if memory_id == None:
            memory_id = str(uuid.uuid4())

        self.db_session.add(
            ChatSessionModel(
                app_id=app_id,
                id=memory_id,
                user_name=user_name,
                user_id=user_id,
                session_id=session_id,
                created_at=created_at,
                metadata= "{}",
            )
        )
        try:
            self.db_session.commit()
        except Exception as e:
            logger.error(f"Error adding chat session to db: {e}")
            self.db_session.rollback()
            return None

        logger.debug(f"Added chat session to db with id: {memory_id}, app_id: {app_id}, user_name: {user_name}, user_id: {user_id}, session_id: {session_id}")
        return memory_id
    

    
    def add_run(self,
            agent_id: Optional[str] = None, 
            user_name: Optional[str] = None,
            user_id: Optional[str] = None, 
            run_id: Optional[str] = None, 
            memory_id: Optional[str] = None,
            created_at: Optional[datetime] = None,
            ) -> Optional[str]:
        
        if not any([agent_id, user_name,user_id, run_id]):
            raise ValueError("One of agent_id, user_id, run_id must be provided")
        
        if memory_id == None:
            memory_id = str(uuid.uuid4())

        self.db_session.add(
            MemoryRunModel(
                agent_id=agent_id,
                id=memory_id,
                user_name=user_name,
                user_id=user_id,
                run_id=run_id,
                created_at=created_at,
                metadata= "{}",
            )
        )
        try:
            self.db_session.commit()
        except Exception as e:
            logger.error(f"Error adding memory run to db: {e}")
            self.db_session.rollback()
            return None

        logger.debug(f"Added memory run to db with id: {memory_id}, agent_id: {agent_id}, user_name: {user_name}, user_id: {user_id}, run_id: {run_id}")
        return memory_id


    def delete(self, app_id: Optional[str] = None, user_name: Optional[str] = None, user_id: Optional[str] = None, session_id: Optional[str] = None):
        """
        Delete all chat history for a given app_id and session_id.
        This is useful for deleting chat history for a given user.

        :param app_id: The app_id to delete chat history for
        :param session_id: The session_id to delete chat history for

        :return: None
        """
        logger.debug(f"Deleting chat history for app_id: {app_id}, user_name: {user_name}, user_id: {user_id}, session_id: {session_id}")
        params = None
        if app_id:
            params = {"app_id": app_id}
        if user_name:
            params["user_name"] = user_name
        if user_id:
            params["user_id"] = user_id
        if session_id:
            params["session_id"] = session_id
        if params != None:
            self.db_session.query(ChatHistoryModel).filter_by(**params).delete()
        else:
            self.db_session.query(ChatHistoryModel).delete()
        try:
            self.db_session.commit()
        except Exception as e:
            logger.error(f"Error deleting chat history: {e}")
            self.db_session.rollback()


    def delete_session(self, app_id: Optional[str] = None, user_name: Optional[str] = None, user_id: Optional[str] = None, session_id: Optional[str] = None):
        """
        Delete all chat history for a given app_id and session_id.
        This is useful for deleting chat history for a given user.

        :param app_id: The app_id to delete chat history for
        :param session_id: The session_id to delete chat history for

        :return: None
        """
        logger.debug(f"Deleting chat session for app_id: {app_id}, user_name: {user_name}, user_id: {user_id}, session_id: {session_id}")
        params = None
        if app_id:
            params = {"app_id": app_id}
        if user_name:
            params["user_name"] = user_name
        if user_id:
            params["user_id"] = user_id
        if session_id:
            params["session_id"] = session_id
        if params != None:
            self.db_session.query(ChatSessionModel).filter_by(**params).delete()
        else:
            self.db_session.query(ChatSessionModel).delete()
        try:
            self.db_session.commit()
        except Exception as e:
            logger.error(f"Error deleting chat session: {e}")
            self.db_session.rollback()


    def delete_run(self, agent_id: Optional[str] = None, user_name: Optional[str] = None, user_id: Optional[str] = None, run_id: Optional[str] = None):
        """
        Delete all chat history for a given app_id and session_id.
        This is useful for deleting chat history for a given user.

        :param agent_id: The agent_id to delete memory history for
        :param run_id: The run_id to delete memory history for

        :return: None
        """
        logger.debug(f"Deleting memory run for agent: {agent_id}, user_name: {user_name}, user_id: {user_id}, run_id: {run_id}")
        params = None
        if agent_id:
            params = {"app_id": agent_id}
        if user_name:
            params["user_name"] = user_name
        if user_id:
            params["user_id"] = user_id
        if run_id:
            params["run_id"] = run_id
        if params != None:
            self.db_session.query(MemoryRunModel).filter_by(**params).delete()
        else:
            self.db_session.query(MemoryRunModel).delete()
        try:
            self.db_session.commit()
        except Exception as e:
            logger.error(f"Error deleting memory run: {e}")
            self.db_session.rollback()

    def get(
        self, app_id: Optional[str] = None, user_name: Optional[str] = None, user_id: Optional[str] = None, session_id: Optional[str] = None, num_rounds=10, fetch_all: bool = False, display_format=False, desc: bool = True
    ) -> list[ChatMessage]:
        """
        Get the chat history for a given app_id.

        param: app_id - The app_id to get chat history
        param: user_name (optional) - The session_id to get chat history. Defaults to "default"
        param: user_id (optional) - The session_id to get chat history. Defaults to "default"
        param: session_id (optional) - The session_id to get chat history. Defaults to "default"
        param: num_rounds (optional) - The number of rounds to get chat history. Defaults to 10
        param: fetch_all (optional) - Whether to fetch all chat history or not. Defaults to False
        param: display_format (optional) - Whether to return the chat history in display format. Defaults to False
        """
        params = None
        if not fetch_all:
            if app_id:
                params = {"app_id": app_id}
            if user_name:
                params["user_name"] = user_name
            if user_id:
                params["user_id"] = user_id
            #if session_id:
            #    params["session_id"] = session_id

        result = ()
        if desc:
            if params == None:
                results = (
                    self.db_session.query(ChatHistoryModel).order_by(ChatHistoryModel.created_at.desc())
                )
            else:
                results = (
                    self.db_session.query(ChatHistoryModel).filter_by(**params).order_by(ChatHistoryModel.created_at.desc())
                )
        else:
            if params == None:
                results = (
                    self.db_session.query(ChatHistoryModel).order_by(ChatHistoryModel.created_at.asc())
                )
            else:
                results = (
                    self.db_session.query(ChatHistoryModel).filter_by(**params).order_by(ChatHistoryModel.created_at.asc())
                )

        results = results.limit(num_rounds) if not fetch_all else results
        history = []
        for result in results:
            metadata = self._deserialize_json(metadata=result.meta_data or "{}")
            # Return list of dict if display_format is True
            if display_format:
                history.append(
                    {
                        "app_id": result.app_id,
                        "user_name": result.user_name,
                        "user_id": result.user_id,
                        "session_id": result.session_id,
                        "human": result.question,
                        "ai": result.answer,
                        "metadata": result.meta_data,
                        "timestamp": result.created_at,
                    }
                )
            else:
                memory = ChatMessage()
                memory.add_user_message(result.question, metadata=metadata)
                memory.add_ai_message(result.answer, metadata=metadata)
                memory.timestamp = result.created_at
                history.append(memory)
        if desc:
            history.reverse()
        return history
    

    def get_sessions(
        self, app_id: Optional[str] = None, user_name: Optional[str] = None, user_id: Optional[str] = None, session_id: Optional[str] = None, num_rounds=10, fetch_all: bool = False, desc: bool = True) -> list:
        """
        Get the chat history for a given app_id.

        param: app_id - The app_id to get chat history
        param: user_name (optional) - The session_id to get chat history. Defaults to "default"
        param: user_id (optional) - The session_id to get chat history. Defaults to "default"
        param: session_id (optional) - The session_id to get chat history. Defaults to "default"
        param: num_rounds (optional) - The number of rounds to get chat history. Defaults to 10
        param: fetch_all (optional) - Whether to fetch all chat history or not. Defaults to False
        """
        params = None
        if not fetch_all:
            if app_id:
                params = {"app_id": app_id}
            if user_name:
                params["user_name"] = user_name
            if user_id:
                params["user_id"] = user_id
            if session_id:
                params["session_id"] = session_id

        result = ()
        if desc:
            if params == None:
                results = (
                    self.db_session.query(ChatSessionModel).order_by(ChatSessionModel.created_at.desc())
                )
            else:
                results = (
                    self.db_session.query(ChatSessionModel).filter_by(**params).order_by(ChatSessionModel.created_at.desc())
                )
        else:
            if params == None:
                results = (
                    self.db_session.query(ChatSessionModel).order_by(ChatSessionModel.created_at.asc())
                )
            else:
                results = (
                    self.db_session.query(ChatSessionModel).filter_by(**params).order_by(ChatSessionModel.created_at.asc())
                )

        results = results.limit(num_rounds) if not fetch_all else results
        history = []
        for result in results:
            metadata = self._deserialize_json("{}")
            # Return list of dict if display_format is True
            history.append(
                {
                    "app_id": result.app_id,
                    "user_name": result.user_name,
                    "user_id": result.user_id,
                    "session_id": result.session_id,
                    "metadata": metadata,
                    "created_at": result.created_at,
                }
            )
        if desc:
            history.reverse()
        return history
    

    def get_runs(
        self, agent_id: Optional[str] = None, user_name: Optional[str] = None, user_id: Optional[str] = None, run_id: Optional[str] = None, num_rounds=10, fetch_all: bool = False, desc: bool = True) -> list:
        """
        Get the chat history for a given agent_id.

        param: agent_id - The agent_id to get memory history
        param: user_name (optional) - The session_id to get chat history. Defaults to "default"
        param: user_id (optional) - The session_id to get chat history. Defaults to "default"
        param: run_id (optional) - The run_id to get chat history. Defaults to "default"
        param: num_rounds (optional) - The number of rounds to get chat history. Defaults to 10
        param: fetch_all (optional) - Whether to fetch all chat history or not. Defaults to False
        """
        params = None
        if not fetch_all:
            if agent_id:
                params = {"agent_id": agent_id}
            if user_name:
                params["user_name"] = user_name
            if user_id:
                params["user_id"] = user_id
            if run_id:
                params["run_id"] = run_id

        result = ()
        if desc:
            if params == None:
                results = (
                    self.db_session.query(MemoryRunModel).order_by(MemoryRunModel.created_at.desc())
                )
            else:
                results = (
                    self.db_session.query(MemoryRunModel).filter_by(**params).order_by(MemoryRunModel.created_at.desc())
                )
        else:
            if params == None:
                results = (
                    self.db_session.query(MemoryRunModel).order_by(MemoryRunModel.created_at.asc())
                )
            else:
                results = (
                    self.db_session.query(MemoryRunModel).filter_by(**params).order_by(MemoryRunModel.created_at.asc())
                )            
        results = results.limit(num_rounds) if not fetch_all else results
        history = []
        for result in results:
            metadata = self._deserialize_json("{}")
            # Return list of dict if display_format is True
            history.append(
                {
                    "agent_id": result.agent_id,
                    "user_name": result.user_name,
                    "user_id": result.user_id,
                    "run_id": result.run_id,
                    "metadata": metadata,
                    "created_at": result.created_at,
                }
            )
        if desc:
            history.reverse()
        return history
    

    def count(self, app_id: Optional[str] = None, user_name: Optional[str] = None, user_id: Optional[str] = None, session_id: Optional[str] = None):
        """
        Count the number of chat messages for a given app_id and session_id.

        :param app_id: The app_id to count chat history for
        :param session_id: The session_id to count chat history for

        :return: The number of chat messages for a given app_id and session_id
        """
        # Rewrite the logic below with sqlalchemy
        params = None
        if app_id:
            params = {"app_id": app_id}
        if user_name:
            params["user_name"] = user_name
        if user_id:
            params["user_id"] = user_id
        if session_id:
            params["session_id"] = session_id
        if params != None:
            return self.db_session.query(ChatHistoryModel).filter_by(**params).count()
        else:
            return self.db_session.query(ChatHistoryModel).count()
        
    

    def count_sessions(self, app_id: Optional[str] = None, user_name: Optional[str] = None, user_id: Optional[str] = None, session_id: Optional[str] = None):
        """
        Count the number of chat messages for a given app_id and session_id.

        :param app_id: The app_id to count chat history for
        :param session_id: The session_id to count chat history for

        :return: The number of chat messages for a given app_id and session_id
        """
        # Rewrite the logic below with sqlalchemy
        params = None
        if app_id:
            params = {"app_id": app_id}
        if user_name:
            params["user_name"] = user_name
        if user_id:
            params["user_id"] = user_id
        if session_id:
            params["session_id"] = session_id
        if params != None:
            return self.db_session.query(ChatSessionModel).filter_by(**params).count()
        else:
            return self.db_session.query(ChatSessionModel).count()
        

    def count_runs(self, agent_id: Optional[str] = None, user_name: Optional[str] = None, user_id: Optional[str] = None, run_id: Optional[str] = None):
        """
        Count the number of chat messages for a given app_id and session_id.

        :param agent_id: The agent_id to count chat history for
        :param run_id: The run_id to count memory history for

        :return: The number of MemoryRunModel for a given app_id and session_id
        """
        # Rewrite the logic below with sqlalchemy
        params = None
        if agent_id:
            params = {"app_id": agent_id}
        if user_name:
            params["user_name"] = user_name
        if user_id:
            params["user_id"] = user_id
        if run_id:
            params["run_id"] = run_id
        if params != None:
            return self.db_session.query(MemoryRunModel).filter_by(**params).count()
        else:
            return self.db_session.query(MemoryRunModel).count()
        

    @staticmethod
    def _serialize_json(metadata: dict[str, Any]):
        return json.dumps(metadata)

    @staticmethod
    def _deserialize_json(metadata: str):
        return json.loads(metadata)

    def close_connection(self):
        self.connection.close()