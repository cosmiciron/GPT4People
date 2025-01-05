from pathlib import Path
import sys
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, Mock, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from llm.llmService import LLMServiceManager


@pytest.fixture
def llm_service_manager():
    return LLMServiceManager()

@pytest.mark.asyncio
async def test_start_and_restart_all_apps(llm_service_manager):
    with patch.object(llm_service_manager, 'run_memory_llm', returns=AsyncMock) as mock_run_memory_llm, \
         patch.object(llm_service_manager, 'run_embedding_llm', returns=AsyncMock) as mock_run_embedding_llm, \
         patch.object(llm_service_manager, 'start_all_apps', wraps=llm_service_manager.start_all_apps) as mock_start_all_apps, \
         patch('asyncio.create_task', new_callable=AsyncMock) as mock_create_task:

        # Mock asyncio.create_task to return a completed Future
        mock_create_task.return_value = asyncio.Future()
        mock_create_task.return_value.set_result([])

        # Run start_all_apps
        await llm_service_manager.start_all_apps()

        # Assertions to ensure start_all_apps was called correctly
        mock_run_memory_llm.assert_awaited_once()
        mock_run_embedding_llm.assert_awaited_once()
        assert mock_create_task.call_count == 2  # Ensure that two tasks were created

        # Mock gather_task for restart_all_apps
        llm_service_manager.gather_task = asyncio.Future()
        llm_service_manager.gather_task.set_result([])

        # Run restart_all_apps
        await llm_service_manager.restart_all_apps()

        # Assertions to ensure restart_all_apps was called correctly
        llm_service_manager.gather_task.cancel()
        await asyncio.gather(llm_service_manager.gather_task, return_exceptions=True)
        mock_start_all_apps.assert_called_once()
        assert mock_create_task.call_count == 4  # Ensure that two more tasks were created during restart

@pytest.mark.asyncio
async def test_run(llm_service_manager):
    with patch.object(llm_service_manager, 'start_all_apps', new_callable=AsyncMock) as mock_start_all_apps, \
         patch.object(llm_service_manager, 'restart_all_apps', new_callable=AsyncMock) as mock_restart_all_apps, \
         patch.object(llm_service_manager, 'stop_all_apps', new_callable=AsyncMock) as mock_stop_all_apps:

        await llm_service_manager.run()

        mock_start_all_apps.assert_awaited_once()
        mock_restart_all_apps.assert_awaited_once()
        mock_stop_all_apps.assert_awaited_once()