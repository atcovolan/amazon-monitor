import os
import json
import shutil
import logging
from threading import RLock
from typing import Dict, Any, List, Optional
from backend.app.storage.base import StorageInterface

logger = logging.getLogger(__name__)

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        from decimal import Decimal
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)

class JsonStorage(StorageInterface):
    def __init__(self, data_dir: str = "data"):
        self.data_dir = os.path.abspath(data_dir)
        self.history_dir = os.path.join(self.data_dir, "history")
        self.backup_dir = os.path.join(self.data_dir, "backups")
        
        self.monitors_file = os.path.join(self.data_dir, "monitors.json")
        self.settings_file = os.path.join(self.data_dir, "settings.json")
        
        self.lock = RLock()  # reentrante: get_monitor() chama get_monitors()
        self._ensure_dirs_and_files()

    def _ensure_dirs_and_files(self):
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.history_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        
        if not os.path.exists(self.monitors_file):
            self._write_atomic(self.monitors_file, {"monitors": []})
            
        if not os.path.exists(self.settings_file):
            self._write_atomic(self.settings_file, {
                "discord_webhook": None,
                "default_check_interval": 300,
                "theme": "dark",
                "currency": "BRL"
            })

    def _write_atomic(self, file_path: str, data: Any):
        temp_file = file_path + ".tmp"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, cls=DecimalEncoder, ensure_ascii=False, indent=2)
            
            # Validar conteudo lendo de volta
            with open(temp_file, 'r', encoding='utf-8') as f:
                json.load(f)
                
            # Substituicao atomica
            if os.path.exists(file_path):
                # Criar backup
                if file_path == self.monitors_file:
                    backup_path = os.path.join(self.backup_dir, "monitors.backup.json")
                    shutil.copy2(file_path, backup_path)
                elif file_path == self.settings_file:
                    backup_path = os.path.join(self.backup_dir, "settings.backup.json")
                    shutil.copy2(file_path, backup_path)
                    
            os.replace(temp_file, file_path)
        except Exception as e:
            logger.error(f"Erro na escrita atomica para {file_path}: {e}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
            raise e

    def _read_json(self, file_path: str, is_monitors: bool = False) -> Any:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erro ao ler arquivo {file_path}: {e}")
            # Tentar recuperar de backup se for monitor ou settings
            if is_monitors and file_path == self.monitors_file:
                backup_path = os.path.join(self.backup_dir, "monitors.backup.json")
                if os.path.exists(backup_path):
                    logger.warning(f"Tentando restaurar monitors.json a partir do backup")
                    try:
                        with open(backup_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        self._write_atomic(self.monitors_file, data)
                        return data
                    except Exception as backup_err:
                        logger.error(f"Erro ao restaurar backup de monitors: {backup_err}")
            elif not is_monitors and file_path == self.settings_file:
                backup_path = os.path.join(self.backup_dir, "settings.backup.json")
                if os.path.exists(backup_path):
                    logger.warning(f"Tentando restaurar settings.json a partir do backup")
                    try:
                        with open(backup_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        self._write_atomic(self.settings_file, data)
                        return data
                    except Exception as backup_err:
                        logger.error(f"Erro ao restaurar backup de settings: {backup_err}")
            raise e

    def get_monitors(self) -> List[Dict[str, Any]]:
        with self.lock:
            data = self._read_json(self.monitors_file, is_monitors=True)
            return data.get("monitors", [])

    def get_monitor(self, monitor_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            monitors = self.get_monitors()
            for m in monitors:
                if m.get("id") == monitor_id:
                    return m
            return None

    def create_monitor(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            monitors_data = self._read_json(self.monitors_file, is_monitors=True)
            monitors = monitors_data.get("monitors", [])
            monitors.append(data)
            monitors_data["monitors"] = monitors
            self._write_atomic(self.monitors_file, monitors_data)
            
            # Criar arquivo de historico inicial
            history_file = os.path.join(self.history_dir, f"{data['id']}.json")
            if not os.path.exists(history_file):
                self._write_atomic(history_file, {
                    "monitor_id": data["id"],
                    "history": []
                })
                
            return data

    def update_monitor(self, monitor_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with self.lock:
            monitors_data = self._read_json(self.monitors_file, is_monitors=True)
            monitors = monitors_data.get("monitors", [])
            updated_monitor = None
            for i, m in enumerate(monitors):
                if m.get("id") == monitor_id:
                    monitors[i] = {**m, **data}
                    updated_monitor = monitors[i]
                    break
            if updated_monitor:
                monitors_data["monitors"] = monitors
                self._write_atomic(self.monitors_file, monitors_data)
            return updated_monitor

    def delete_monitor(self, monitor_id: str) -> bool:
        with self.lock:
            monitors_data = self._read_json(self.monitors_file, is_monitors=True)
            monitors = monitors_data.get("monitors", [])
            initial_len = len(monitors)
            monitors = [m for m in monitors if m.get("id") != monitor_id]
            if len(monitors) < initial_len:
                monitors_data["monitors"] = monitors
                self._write_atomic(self.monitors_file, monitors_data)
                
                # Tratar arquivo de historico (deletar ou manter como backup)
                history_file = os.path.join(self.history_dir, f"{monitor_id}.json")
                if os.path.exists(history_file):
                    try:
                        os.remove(history_file)
                    except Exception as e:
                        logger.error(f"Erro ao remover historico de {monitor_id}: {e}")
                return True
            return False

    def get_settings(self) -> Dict[str, Any]:
        with self.lock:
            return self._read_json(self.settings_file)

    def update_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with self.lock:
            current_settings = self._read_json(self.settings_file)
            updated = {**current_settings, **data}
            self._write_atomic(self.settings_file, updated)
            return updated

    def append_history(self, monitor_id: str, entry: Dict[str, Any]) -> None:
        with self.lock:
            history_file = os.path.join(self.history_dir, f"{monitor_id}.json")
            history_data = {"monitor_id": monitor_id, "history": []}
            if os.path.exists(history_file):
                try:
                    history_data = self._read_json(history_file)
                except Exception:
                    pass
            history = history_data.get("history", [])
            history.append(entry)
            history_data["history"] = history
            self._write_atomic(history_file, history_data)

    def get_history(self, monitor_id: str) -> List[Dict[str, Any]]:
        with self.lock:
            history_file = os.path.join(self.history_dir, f"{monitor_id}.json")
            if os.path.exists(history_file):
                try:
                    data = self._read_json(history_file)
                    return data.get("history", [])
                except Exception:
                    return []
            return []
