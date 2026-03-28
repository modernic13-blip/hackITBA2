"""
pipeline.py -- SignalPipeline: main orchestrator for the 8-stage ML pipeline.

Runs all stages sequentially:
    M1 Ingestion -> M2 Features -> M3 Filtering -> M4 Labeling ->
    M5 Splitting -> M6 Feature Selection -> M7 Modeling -> M8 Evaluation

Also provides auto-search methods for hyperparameter optimization
of the filtering (M3) and labeling (M4) stages.

No AWS/S3 dependencies. No dollar bars. Local data only.
"""

import gc
import json
import time
import hashlib
import subprocess
from datetime import datetime
from pathlib import Path
import copy
import numpy as np

from .base_module import StageBase
from .pipeline_data import PipelineData
from .config_loader import load_config

from ..modules.ingestion import IngestionModule
from ..modules.features import FeaturesModule, _detect_freq_minutes, _parse_timeframe_str
from ..modules.filtering import FilteringModule
from ..modules.labeling import LabelingModule
from ..modules.splitting import SplittingModule
from ..modules.feature_selection import FeatureSelectionModule
from ..modules.modeling import ModelingModule
from ..modules.evaluation import EvaluationModule


# ---------------------------------------------------------------------------
# Module registry
# ---------------------------------------------------------------------------

_MODULE_REGISTRY = {
    "ingestion": IngestionModule,
    "features": FeaturesModule,
    "filtering": FilteringModule,
    "labeling": LabelingModule,
    "splitting": SplittingModule,
    "feature_selection": FeatureSelectionModule,
    "modeling": ModelingModule,
    "evaluation": EvaluationModule,
}

_DEFAULT_STAGE_ORDER = [
    "ingestion",
    "features",
    "filtering",
    "labeling",
    "splitting",
    "feature_selection",
    "modeling",
    "evaluation",
]


def _config_hash(config: dict) -> str:
    """Compute a short deterministic hash for a configuration dict."""
    s = json.dumps(config, sort_keys=True, default=str)
    return hashlib.md5(s.encode()).hexdigest()[:10]


def _git_sha() -> str:
    """Return the current git short SHA, or 'unknown' if not in a repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# SignalPipeline
# ---------------------------------------------------------------------------

class SignalPipeline:
    """
    Main orchestrator that runs the 8-stage ML pipeline.

    Usage:
        pipeline = SignalPipeline("config/my_config.yaml")
        data, success = pipeline.run()
        if success:
            metrics = data.get("metrics")

    Or run a subset of stages:
        data, success = pipeline.run(stages=["ingestion", "features"])

    Auto-search for optimal M3/M4 parameters:
        best = pipeline.auto_search_m3(k_range=[0.3, 0.5, 0.7, 1.0])
    """

    def __init__(self, config_path: str = None, config: dict = None):
        """
        Initialize the pipeline.

        Args:
            config_path: Path to YAML configuration file.
            config: Dict configuration (overrides config_path).
        """
        if config is not None:
            self.config = config
        elif config_path is not None:
            self.config = load_config(config_path)
        else:
            raise ValueError("Provide either config_path or config dict.")

        self.config_path = config_path
        self.run_id = None
        self.traces = []

    def run(
        self,
        stages: list[str] = None,
        data: PipelineData = None,
        verbose: bool = True,
    ) -> tuple[PipelineData, bool]:
        """
        Run the full pipeline or a subset of stages.

        Args:
            stages: List of stage names to run (default: all 8 stages).
            data: Existing PipelineData to continue from (default: new).
            verbose: Print progress messages.

        Returns:
            (PipelineData, success_bool)
        """
        if stages is None:
            stages = _DEFAULT_STAGE_ORDER

        if data is None:
            data = PipelineData()

        self.run_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{_config_hash(self.config)}"
        self.traces = []
        pipeline_start = time.time()

        if verbose:
            asset = self.config.get("asset", "?")
            freq = self.config.get("frequency", "?")
            print(f"\n{'='*60}")
            print(f"  SignalPipeline  |  asset={asset}  freq={freq}")
            print(f"  run_id: {self.run_id}")
            print(f"{'='*60}\n")

        success = True

        for stage_name in stages:
            if stage_name not in _MODULE_REGISTRY:
                if verbose:
                    print(f"  [SKIP] Unknown stage: '{stage_name}'")
                continue

            stage_config = self._get_stage_config(stage_name)
            module_cls = _MODULE_REGISTRY[stage_name]
            module = module_cls(config=stage_config)

            if verbose:
                print(f"  [{stage_name.upper()}] Running...", end="", flush=True)

            data, stage_ok = module.execute(data)
            trace = module.get_trace()
            self.traces.append(trace)

            if verbose:
                status = trace["trace"].get("status", "?")
                duration = trace["trace"].get("duration_seconds", "?")
                print(f" {status} ({duration}s)")

                # Print validation messages
                for msg in trace["trace"].get("validation_messages", []):
                    print(f"    {msg}")

                # Print error if any
                if "error" in trace["trace"]:
                    print(f"    ERROR: {trace['trace']['error']}")

            if not stage_ok:
                success = False
                if verbose:
                    print(f"\n  Pipeline stopped at '{stage_name}'.\n")
                break

        pipeline_end = time.time()
        total_time = round(pipeline_end - pipeline_start, 2)

        if verbose:
            print(f"\n{'='*60}")
            print(f"  Pipeline {'COMPLETED' if success else 'FAILED'} in {total_time}s")
            print(f"{'='*60}\n")

        return data, success

    def run_modules(
        self,
        module_names: list[str],
        data: PipelineData = None,
        verbose: bool = True,
    ) -> tuple[PipelineData, bool]:
        """Alias for run() with specific stages."""
        return self.run(stages=module_names, data=data, verbose=verbose)

    def _get_stage_config(self, stage_name: str) -> dict:
        """
        Build the configuration dict for a specific stage.

        Merges the stage-specific section with relevant top-level keys.
        """
        stage_config = copy.deepcopy(self.config.get(stage_name, {}))

        # Inject top-level keys that stages may need
        top_keys = ["asset", "period", "frequency"]
        for key in top_keys:
            if key in self.config and key not in stage_config:
                stage_config[key] = self.config[key]

        return stage_config

    # ------------------------------------------------------------------
    # Auto-search M3: Sensibilidad CUSUM
    # ------------------------------------------------------------------

    def auto_search_m3(
        self,
        k_range: list[float] = None,
        target_event_ratio: tuple[float, float] = (0.01, 0.10),
        data: PipelineData = None,
        verbose: bool = True,
    ) -> dict:
        """
        Search for optimal Sensibilidad CUSUM (k_Px) in the filtering stage.

        Runs M1+M2 once, then iterates M3 with different k values.
        Selects the k that produces an event ratio within the target range
        and closest to the geometric mean of the range.

        Args:
            k_range: List of k_Px values to try.
                Default: [0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0]
            target_event_ratio: (min_ratio, max_ratio) of events/bars.
            data: Pre-computed PipelineData with M1+M2 results.
            verbose: Print progress.

        Returns:
            Dict with:
                - best_k: optimal k_Px value
                - best_ratio: event ratio at best k
                - results: list of (k, n_events, ratio) for all tried values
        """
        if k_range is None:
            k_range = [0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0]

        # Run M1+M2 if not provided
        if data is None:
            data, ok = self.run(stages=["ingestion", "features"], verbose=verbose)
            if not ok:
                raise RuntimeError("M1+M2 failed. Cannot search M3.")

        close = data.get("close")
        n_bars = len(close)
        target_mid = np.sqrt(target_event_ratio[0] * target_event_ratio[1])

        results = []
        best_k = None
        best_dist = np.inf

        for k in k_range:
            # Create a temporary config for M3
            m3_config = copy.deepcopy(self._get_stage_config("filtering"))
            m3_config["k_Px"] = k

            module = FilteringModule(config=m3_config)
            temp_data = PipelineData()
            temp_data.set("close", close)
            if data.has("volume"):
                temp_data.set("volume", data.get("volume"))

            temp_data, ok = module.execute(temp_data)

            if ok and temp_data.has("tEvents"):
                n_events = len(temp_data.get("tEvents"))
                ratio = n_events / n_bars if n_bars > 0 else 0
            else:
                n_events = 0
                ratio = 0

            results.append({"k": k, "n_events": n_events, "ratio": round(ratio, 4)})

            # Check if within target range
            if target_event_ratio[0] <= ratio <= target_event_ratio[1]:
                dist = abs(ratio - target_mid)
                if dist < best_dist:
                    best_dist = dist
                    best_k = k

            if verbose:
                in_range = "OK" if target_event_ratio[0] <= ratio <= target_event_ratio[1] else "--"
                print(f"  k={k:.2f} -> {n_events} events, ratio={ratio:.4f} [{in_range}]")

        # If no k in range, pick the one closest to target_mid
        if best_k is None:
            for r in results:
                dist = abs(r["ratio"] - target_mid)
                if dist < best_dist:
                    best_dist = dist
                    best_k = r["k"]

        if verbose:
            print(f"\n  Best k_Px = {best_k}")

        return {
            "best_k": best_k,
            "best_ratio": next(
                (r["ratio"] for r in results if r["k"] == best_k), 0
            ),
            "results": results,
        }

    # ------------------------------------------------------------------
    # Auto-search M4: Triple Barrier parameters
    # ------------------------------------------------------------------

    def auto_search_m4(
        self,
        pt_sl_range: list[list[float]] = None,
        vbar_range: list[int] = None,
        target_balance: float = 0.5,
        data: PipelineData = None,
        verbose: bool = True,
    ) -> dict:
        """
        Search for optimal triple barrier parameters.

        Runs M1-M3 once, then iterates M4 with different pt_sl and vertical_bars.
        Selects the combination that produces the most balanced labels
        (closest to target_balance fraction of +1 labels).

        Args:
            pt_sl_range: List of [pt_mult, sl_mult] pairs.
                Default: [[0.5,0.5], [1,1], [1.5,1], [1,1.5], [2,1], [1,2]]
            vbar_range: List of vertical_bars values.
                Default: [25, 50, 100]
            target_balance: Target fraction of +1 labels (0.5 = balanced).
            data: Pre-computed PipelineData with M1-M3 results.
            verbose: Print progress.

        Returns:
            Dict with:
                - best_pt_sl: best [pt, sl] pair
                - best_vbars: best vertical_bars value
                - best_balance: label balance at best params
                - results: list of dicts for all tried combinations
        """
        if pt_sl_range is None:
            pt_sl_range = [
                [0.5, 0.5],
                [1.0, 1.0],
                [1.5, 1.0],
                [1.0, 1.5],
                [2.0, 1.0],
                [1.0, 2.0],
            ]

        if vbar_range is None:
            vbar_range = [25, 50, 100]

        # Run M1-M3 if not provided
        if data is None:
            data, ok = self.run(
                stages=["ingestion", "features", "filtering"], verbose=verbose
            )
            if not ok:
                raise RuntimeError("M1-M3 failed. Cannot search M4.")

        close = data.get("close")
        tEvents = data.get("tEvents")

        results = []
        best_combo = None
        best_dist = np.inf

        for pt_sl in pt_sl_range:
            for vbars in vbar_range:
                m4_config = copy.deepcopy(self._get_stage_config("labeling"))
                m4_config["pt_sl"] = pt_sl
                m4_config["vertical_bars"] = vbars

                module = LabelingModule(config=m4_config)
                temp_data = PipelineData()
                temp_data.set("close", close)
                temp_data.set("tEvents", tEvents)

                temp_data, ok = module.execute(temp_data)

                if ok and temp_data.has("labels"):
                    labels = temp_data.get("labels")
                    n_labels = len(labels)
                    n_pos = int((labels == 1).sum())
                    balance = n_pos / n_labels if n_labels > 0 else 0
                else:
                    n_labels = 0
                    n_pos = 0
                    balance = 0

                entry = {
                    "pt_sl": pt_sl,
                    "vbars": vbars,
                    "n_labels": n_labels,
                    "n_positive": n_pos,
                    "balance": round(balance, 4),
                }
                results.append(entry)

                dist = abs(balance - target_balance)
                if n_labels > 0 and dist < best_dist:
                    best_dist = dist
                    best_combo = entry

                if verbose:
                    print(
                        f"  pt_sl={pt_sl}, vbars={vbars} -> "
                        f"{n_labels} labels, +1={n_pos}, balance={balance:.3f}"
                    )

        if best_combo is None:
            best_combo = {"pt_sl": [1, 1], "vbars": 50, "balance": 0}

        if verbose:
            print(
                f"\n  Best: pt_sl={best_combo['pt_sl']}, "
                f"vbars={best_combo['vbars']}, "
                f"balance={best_combo['balance']}"
            )

        return {
            "best_pt_sl": best_combo["pt_sl"],
            "best_vbars": best_combo["vbars"],
            "best_balance": best_combo["balance"],
            "results": results,
        }

    # ------------------------------------------------------------------
    # Run record and persistence
    # ------------------------------------------------------------------

    def get_run_record(self) -> dict:
        """
        Return a complete record of the pipeline run for logging.

        Includes: run_id, config hash, git SHA, timestamps, all traces.
        """
        return {
            "run_id": self.run_id,
            "config_hash": _config_hash(self.config),
            "git_sha": _git_sha(),
            "timestamp": datetime.now().isoformat(),
            "asset": self.config.get("asset"),
            "frequency": self.config.get("frequency"),
            "period": self.config.get("period"),
            "config": self.config,
            "traces": self.traces,
        }

    def save_run(self, output_dir: str = "runs") -> str:
        """
        Save the run record to a JSON file.

        Args:
            output_dir: Directory to save the run record.

        Returns:
            Path to the saved file.
        """
        record = self.get_run_record()
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        filename = f"{self.run_id}.json"
        filepath = out_path / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, default=str)

        return str(filepath)

    # ------------------------------------------------------------------
    # Convenience: full run with auto-search
    # ------------------------------------------------------------------

    def run_with_auto_search(
        self,
        search_m3: bool = True,
        search_m4: bool = True,
        verbose: bool = True,
    ) -> tuple[PipelineData, bool]:
        """
        Run the full pipeline with automatic hyperparameter search for M3 and M4.

        Steps:
            1. Run M1 + M2
            2. (Optional) Auto-search M3 and update config
            3. (Optional) Auto-search M4 and update config
            4. Run M3 through M8

        Args:
            search_m3: Whether to auto-search filtering parameters.
            search_m4: Whether to auto-search labeling parameters.
            verbose: Print progress.

        Returns:
            (PipelineData, success_bool)
        """
        # Step 1: Run M1 + M2
        data, ok = self.run(stages=["ingestion", "features"], verbose=verbose)
        if not ok:
            return data, False

        # Step 2: Auto-search M3
        if search_m3:
            if verbose:
                print("\n--- Auto-search M3 (Sensibilidad CUSUM) ---")
            m3_result = self.auto_search_m3(data=data, verbose=verbose)
            best_k = m3_result["best_k"]
            if best_k is not None:
                self.config.setdefault("filtering", {})["k_Px"] = best_k

        # Step 3: Run M3
        data, ok = self.run(stages=["filtering"], data=data, verbose=verbose)
        if not ok:
            return data, False

        # Step 4: Auto-search M4
        if search_m4:
            if verbose:
                print("\n--- Auto-search M4 (Triple Barrier) ---")
            m4_result = self.auto_search_m4(data=data, verbose=verbose)
            self.config.setdefault("labeling", {})["pt_sl"] = m4_result["best_pt_sl"]
            self.config.setdefault("labeling", {})["vertical_bars"] = m4_result["best_vbars"]

        # Step 5: Run M4 through M8
        remaining = ["labeling", "splitting", "feature_selection", "modeling", "evaluation"]
        data, ok = self.run(stages=remaining, data=data, verbose=verbose)

        return data, ok

    # ------------------------------------------------------------------
    # Convenience: get final metrics
    # ------------------------------------------------------------------

    def get_metrics(self, data: PipelineData) -> dict:
        """Extract metrics from pipeline data, if available."""
        return data.get("metrics", required=False) or {}

    def get_model(self, data: PipelineData):
        """Extract the trained model from pipeline data."""
        return data.get("model", required=False)

    def __repr__(self):
        asset = self.config.get("asset", "?")
        freq = self.config.get("frequency", "?")
        return f"SignalPipeline(asset={asset}, freq={freq})"
