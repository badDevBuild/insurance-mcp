import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from src.crawler.acquisition.downloader import PDFDownloader
from pathlib import Path

@pytest.mark.asyncio
async def test_downloader_retry_success():
    """Test that downloader retries on failure and succeeds."""
    downloader = PDFDownloader(max_retries=3, initial_delay=0.1)
    
    with patch('aiohttp.ClientSession') as mock_session_cls:
        # Mock the session object
        mock_session = MagicMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        
        # Prepare mock responses
        mock_resp_fail = AsyncMock()
        mock_resp_fail.status = 500
        
        mock_resp_success = AsyncMock()
        mock_resp_success.status = 200
        mock_resp_success.read.return_value = b"pdf content"
        
        # Setup mock_session.get to return a context manager
        # The context manager's __aenter__ should return the response
        # We need side_effect on __aenter__ to return different responses
        mock_get_ctx = MagicMock()
        mock_session.get.return_value = mock_get_ctx
        mock_get_ctx.__aenter__.side_effect = [mock_resp_fail, mock_resp_success]
        
        target_path = Path("/tmp/test.pdf")
        with patch("builtins.open", new_callable=MagicMock):
             success = await downloader.download("http://example.com", target_path)
             
        assert success is True
        # Should have called get twice
        assert mock_session.get.call_count == 2

@pytest.mark.asyncio
async def test_downloader_max_retries_exceeded():
    """Test that downloader fails after max retries."""
    downloader = PDFDownloader(max_retries=2, initial_delay=0.1)
    
    with patch('aiohttp.ClientSession') as mock_session_cls:
        mock_session = MagicMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        
        mock_resp_fail = AsyncMock()
        mock_resp_fail.status = 500
        
        mock_get_ctx = MagicMock()
        mock_session.get.return_value = mock_get_ctx
        mock_get_ctx.__aenter__.return_value = mock_resp_fail
        
        target_path = Path("/tmp/test_fail.pdf")
        success = await downloader.download("http://example.com", target_path)
             
        assert success is False
        # Should have called get 2 times (max_retries)
        assert mock_session.get.call_count == 2
