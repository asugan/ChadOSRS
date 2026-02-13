from __future__ import annotations

import argparse
from pathlib import Path

from bot_core.engine import BotEngine
from bot_core.runtime import build_adapters, load_app_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run bot core demo")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/dev.json"),
        help="Path to JSON config",
    )
    args = parser.parse_args()

    app_config = load_app_config(args.config)
    perception, runner = build_adapters(app_config)

    print(f"runner={runner.__class__.__name__}")

    if hasattr(perception, "listen_port"):
        print(f"telemetry_listen_port={getattr(perception, 'listen_port')}")

    engine = BotEngine.default(
        perception=perception,
        runner=runner,
        config=app_config.engine,
    )
    try:
        result = engine.run()
    except RuntimeError as exc:
        print(f"run_error={exc}")
        return
    finally:
        if hasattr(perception, "close"):
            getattr(perception, "close")()

    print("Run finished")
    print(f"mode={app_config.adapter_mode}")
    print(f"success={result.success}")
    print(f"reason={result.reason}")
    print(f"ticks={result.ticks}")
    print(f"final_state={result.final_state}")
    print(f"log_path={result.log_path}")


if __name__ == "__main__":
    main()
