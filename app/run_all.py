import argparse
import subprocess
import sys
import time


# Все долгоживущие воркеры конвейера. Каждый запускается отдельным процессом,
# поэтому падение одного не роняет остальные.
WORKERS = [
    "app.workers.vk_scraper_worker",
    "app.workers.tg_scraper_worker",
    "app.workers.coarse_filter_worker",
    "app.workers.ml_filter_worker",
    "app.workers.attribute_extractor_worker",
    "app.workers.vk_group_publisher_worker",
    "app.workers.tg_channel_publisher_worker",
    "app.workers.tg_bot_worker",
    "app.workers.vk_bot_worker",
]

RESTART_DELAY = 5.0          # пауза перед перезапуском упавшего воркера, с
MAX_RESTARTS = 5             # сколько раз подряд перезапускать, прежде чем сдаться


def spawn(module: str) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-m", module])


def main() -> None:
    parser = argparse.ArgumentParser(description="Запуск всех воркеров конвейера.")
    parser.add_argument("--only", help="Запустить только перечисленные модули через запятую")
    parser.add_argument("--no-restart", action="store_true", help="Не перезапускать упавшие воркеры")
    args = parser.parse_args()

    workers = WORKERS
    if args.only:
        wanted = {w.strip() for w in args.only.split(",")}
        workers = [w for w in WORKERS if w in wanted or w.split(".")[-1] in wanted]

    procs: dict[str, subprocess.Popen] = {}
    restarts: dict[str, int] = {w: 0 for w in workers}

    for module in workers:
        procs[module] = spawn(module)
        print(f"[run_all] запущен {module} (pid {procs[module].pid})", flush=True)

    try:
        while True:
            time.sleep(1.0)
            for module, proc in list(procs.items()):
                if proc.poll() is None:
                    continue
                code = proc.returncode
                print(f"[run_all] {module} завершился (код {code})", flush=True)

                if args.no_restart or restarts[module] >= MAX_RESTARTS:
                    if not args.no_restart:
                        print(f"[run_all] {module}: достигнут предел перезапусков, не поднимаю", flush=True)
                    del procs[module]
                    continue

                restarts[module] += 1
                time.sleep(RESTART_DELAY)
                procs[module] = spawn(module)
                print(f"[run_all] перезапущен {module} (попытка {restarts[module]})", flush=True)

            if not procs:
                print("[run_all] все воркеры остановлены, выход", flush=True)
                break
    except KeyboardInterrupt:
        print("\n[run_all] остановка всех воркеров...", flush=True)
    finally:
        for module, proc in procs.items():
            if proc.poll() is None:
                proc.terminate()
        for module, proc in procs.items():
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("[run_all] готово", flush=True)


if __name__ == "__main__":
    main()
