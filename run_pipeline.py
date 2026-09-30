import subprocess
import sys
import time


PIPELINE = [
    ("Article Collection", "collect.py"),
    ("Initial Analysis", "analyze.py"),
    ("Contextual Research", "research.py"),
    ("Assessment", "assessment.py"),
    ("Report Generation", "generate_report.py"),
]


def run_stage(name, script):

    print("\n" + "=" * 60)
    print(f"Starting: {name}")
    print("=" * 60)

    start_time = time.time()

    result = subprocess.run(
        [sys.executable, script]
    )

    elapsed = time.time() - start_time

    if result.returncode != 0:
        print(f"\n{name} FAILED after {elapsed:.2f} seconds.")
        print("Pipeline stopped.")
        sys.exit(result.returncode)

    print(
        f"{name} completed successfully "
        f"in {elapsed:.2f} seconds."
    )


def main():

    print("\nStarting Intelligence Gathering Pipeline")

    pipeline_start = time.time()

    for name, script in PIPELINE:
        run_stage(name, script)

    total_time = time.time() - pipeline_start

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print(f"Total runtime: {total_time:.2f} seconds")
    print("=" * 60)


if __name__ == "__main__":
    main()