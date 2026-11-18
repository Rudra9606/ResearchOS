"""Safe CSV/XLSX exploratory data analysis."""

from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np
import pandas as pd
from sqlalchemy import select

from app.agents.base import BaseAgent
from app.models.document import Document


class DataAnalystAgent(BaseAgent):
    """Analyze tabular documents without executing uploaded code."""

    def __init__(self, *, db=None, user_id=None, project_id=None):
        super().__init__(name="Data Analyst")
        self.db = db
        self.user_id = user_id
        self.project_id = project_id

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        results = [
            await self._analyze_dataset(dataset_id, state)
            for dataset_id in state.get("dataset_ids", [])
        ]
        state["data_analysis_results"] = results
        state["data_analysis_status"] = (
            "failed"
            if any(result["status"] == "failed" for result in results)
            else "completed"
            if results
            else "no_results"
        )
        state["current_step"] = "data_analysis_completed"
        state["agents_completed"] = state.get("agents_completed", []) + ["data_analyst"]
        return state

    async def _analyze_dataset(
        self, dataset_id: str | UUID, state: dict[str, Any]
    ) -> dict[str, Any]:
        base = {
            "dataset_id": str(dataset_id),
            "summary": {},
            "statistics": {},
            "missing_values": {},
            "duplicate_rows": 0,
            "outliers": {},
            "findings": [],
            "chart_specs": [],
        }
        try:
            path = self._resolve_dataset(dataset_id, state)
            frame = self._read_frame(path)
            if frame.empty and len(frame.columns) == 0:
                return {**base, "status": "no_results"}
            numeric = frame.select_dtypes(include=[np.number])
            statistics = self._json_safe(numeric.describe().to_dict())
            missing = {
                str(column): int(value)
                for column, value in frame.isna().sum().items()
                if int(value)
            }
            outliers = self._find_outliers(numeric)
            findings = self._findings(frame, missing, outliers)
            return {
                **base,
                "status": "completed",
                "summary": {
                    "filename": path.name,
                    "rows": int(frame.shape[0]),
                    "columns": int(frame.shape[1]),
                    "column_names": [str(column) for column in frame.columns],
                    "dtypes": {str(column): str(dtype) for column, dtype in frame.dtypes.items()},
                },
                "statistics": statistics,
                "missing_values": missing,
                "duplicate_rows": int(frame.duplicated().sum()),
                "outliers": outliers,
                "findings": findings,
                "chart_specs": self._chart_specs(frame),
            }
        except (ValueError, OSError, TypeError) as exc:
            return {**base, "status": "failed", "error": str(exc)}

    def _resolve_dataset(self, dataset_id: str | UUID, state: dict[str, Any]) -> Path:
        supplied = state.get("dataset_paths", {})
        candidate = supplied.get(str(dataset_id), dataset_id) if isinstance(supplied, dict) else dataset_id
        if self.db is not None:
            try:
                document_id = UUID(str(dataset_id))
            except ValueError as exc:
                raise ValueError("Dataset must reference an owned document.") from exc
            statement = select(Document).where(
                Document.id == document_id,
                Document.user_id == self.user_id,
            )
            if self.project_id is not None:
                statement = statement.where(Document.project_id == self.project_id)
            document = self.db.scalar(statement)
            if document is None:
                raise ValueError("Dataset not found or access denied.")
            candidate = document.file_path
        path = Path(str(candidate)).resolve()
        if not path.is_file() or path.suffix.lower() not in {".csv", ".xlsx"}:
            raise ValueError("Only existing CSV and XLSX datasets are supported.")
        return path

    @staticmethod
    def _read_frame(path: Path) -> pd.DataFrame:
        if path.suffix.lower() == ".csv":
            return pd.read_csv(path)
        return pd.read_excel(path, engine="openpyxl")

    @staticmethod
    def _find_outliers(frame: pd.DataFrame) -> dict[str, int]:
        result = {}
        for column in frame.columns:
            series = frame[column].dropna()
            if series.empty:
                continue
            q1, q3 = series.quantile([0.25, 0.75])
            iqr = q3 - q1
            if iqr == 0:
                result[str(column)] = 0
                continue
            result[str(column)] = int(((series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)).sum())
        return result

    @staticmethod
    def _findings(frame: pd.DataFrame, missing: dict[str, int], outliers: dict[str, int]) -> list[str]:
        findings = []
        if missing:
            findings.append(f"{len(missing)} columns contain missing values.")
        duplicate_count = int(frame.duplicated().sum())
        if duplicate_count:
            findings.append(f"{duplicate_count} duplicate rows detected.")
        unusual = {column: count for column, count in outliers.items() if count}
        if unusual:
            findings.append(f"Outliers detected in {len(unusual)} numeric columns.")
        if not findings:
            findings.append("No missing values, duplicate rows, or IQR outliers detected.")
        return findings

    @staticmethod
    def _chart_specs(frame: pd.DataFrame) -> list[dict[str, Any]]:
        numeric_columns = [str(column) for column in frame.select_dtypes(include=[np.number]).columns]
        if not numeric_columns:
            return []
        charts = []
        for column in numeric_columns[:10]:
            values = frame[column].dropna().to_numpy(dtype=float)
            if not len(values):
                continue
            bin_count = min(12, max(1, int(np.ceil(np.sqrt(len(values))))))
            counts, edges = np.histogram(values, bins=bin_count)
            charts.append({
                "type": "histogram",
                "column": column,
                "counts": [int(count) for count in counts],
                "bin_edges": [float(edge) for edge in edges],
            })
        return charts

    @staticmethod
    def _json_safe(value):
        if isinstance(value, dict):
            return {str(key): DataAnalystAgent._json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [DataAnalystAgent._json_safe(item) for item in value]
        if isinstance(value, (np.integer, np.floating)):
            return value.item()
        if pd.isna(value):
            return None
        return value
