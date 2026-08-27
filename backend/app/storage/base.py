from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class StorageInterface(ABC):
    @abstractmethod
    def get_monitors(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_monitor(self, monitor_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def create_monitor(self, data: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def update_monitor(self, monitor_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def delete_monitor(self, monitor_id: str) -> bool:
        pass

    @abstractmethod
    def get_settings(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def update_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def append_history(self, monitor_id: str, entry: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_history(self, monitor_id: str) -> List[Dict[str, Any]]:
        pass
