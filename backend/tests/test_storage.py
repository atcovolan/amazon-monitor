import os
import shutil
import pytest
from backend.app.storage.json_storage import JsonStorage

@pytest.fixture
def temp_storage(tmp_path):
    storage_dir = tmp_path / "data"
    storage = JsonStorage(data_dir=str(storage_dir))
    return storage

def test_initial_files_creation(temp_storage):
    assert os.path.exists(temp_storage.monitors_file)
    assert os.path.exists(temp_storage.settings_file)
    assert temp_storage.get_monitors() == []
    assert temp_storage.get_settings()["theme"] == "dark"

def test_crud_monitor(temp_storage):
    monitor_data = {
        "id": "test-uuid",
        "name": "Logitech Mouse",
        "asin": "B08PC54QBP",
        "url": "https://www.amazon.com.br/dp/B08PC54QBP",
        "target_price": 500.0,
        "current_price": 550.0,
        "is_active": True,
        "created_at": "2026-08-26T20:00:00",
        "updated_at": "2026-08-26T20:00:00"
    }
    
    # Create
    temp_storage.create_monitor(monitor_data)
    assert len(temp_storage.get_monitors()) == 1
    assert temp_storage.get_monitor("test-uuid")["name"] == "Logitech Mouse"
    
    # Update
    temp_storage.update_monitor("test-uuid", {"name": "G Pro Superlight", "current_price": 490.0})
    updated = temp_storage.get_monitor("test-uuid")
    assert updated["name"] == "G Pro Superlight"
    assert updated["current_price"] == 490.0
    
    # Delete
    temp_storage.delete_monitor("test-uuid")
    assert len(temp_storage.get_monitors()) == 0
    assert temp_storage.get_monitor("test-uuid") is None
