"""
StageBase -- Plantilla base para todos los módulos del pipeline.

Cada módulo hereda from StageBase and implements:
    - validate(): verifica que pipeline_data tenga inputs requeridos
    - run(): ejecuta la lógica del módulo
    - get_trace(): devuelve metadata de ejecución

El contrato 'requires' y 'produces' declara what each stage needs
and generates. This enables automatic input validation and dependency tracking.
"""

import time
from typing import Any
from .pipeline_data import PipelineData


class StageBase:
    """
    Clase base para todos los módulos del pipeline.

    Atributos de clase que cada módulo debe definir:
        name (str): identificador del módulo (e.g., "cusum", "labeling")

        requires (dict): qué necesita del pipeline_data y del config.
            {
                "data": {
                    "close": {"required": True, "desc": "Serie de precios"},
                    "oi":    {"required": False, "desc": "Open Interest"},
                },
                "params": {
                    "k_Px": {"type": "float", "default": 0.5, "desc": "Sensibilidad CUSUM"},
                }
            }

        produces (dict): qué agrega al pipeline_data.
            {
                "tEvents": "DatetimeIndex of significant events",
            }
    """

    name = "base"
    requires = {"data": {}, "params": {}}
    produces = {}

    def __init__(self, config: dict):
        self.config = config
        self.trace = {}
        self._start_time = None
        self._end_time = None

    def validate(self, data: PipelineData) -> tuple[bool, list]:
        """Verifica que pipeline_data tenga todo lo que necesita este módulo."""
        messages = []

        for key, spec in self.requires.get("data", {}).items():
            if "{" in key:
                continue

            if spec.get("required", True) and not data.has(key):
                messages.append(f"MISSING (required): '{key}' -- {spec.get('desc', '')}")
            elif not spec.get("required", True) and not data.has(key):
                messages.append(f"ABSENT (optional): '{key}' -- {spec.get('desc', '')}")

        for param, spec in self.requires.get("params", {}).items():
            if param not in self.config:
                if "default" in spec:
                    self.config[param] = spec["default"]
                else:
                    messages.append(f"MISSING PARAM: '{param}' -- {spec.get('desc', '')}")

        has_errors = any("MISSING" in m and "optional" not in m.lower() for m in messages)
        is_valid = not has_errors

        return is_valid, messages

    def run(self, data: PipelineData) -> PipelineData:
        """Execute stage logic. Override in subclass."""
        raise NotImplementedError(f"Stage '{self.name}' did not implement run()")

    def execute(self, data: PipelineData) -> tuple[PipelineData, bool]:
        """Método principal llamado por el orchestrador del pipeline. Orchestrates: validate -> run -> trace."""
        is_valid, messages = self.validate(data)
        self.trace["validation_messages"] = messages

        if not is_valid:
            self.trace["status"] = "FAILED_VALIDATION"
            return data, False

        self._start_time = time.time()
        try:
            data = self.run(data)
            self._end_time = time.time()
            self.trace["status"] = "OK"
            self.trace["duration_seconds"] = round(self._end_time - self._start_time, 2)
        except Exception as e:
            self._end_time = time.time()
            self.trace["status"] = "FAILED_EXECUTION"
            self.trace["error"] = str(e)
            self.trace["duration_seconds"] = round(self._end_time - self._start_time, 2)
            return data, False

        return data, True

    def get_trace(self) -> dict:
        """Devuelve el registro completo de ejecución de este módulo."""
        return {
            "module": self.name,
            "config": self.config,
            "trace": self.trace,
        }
