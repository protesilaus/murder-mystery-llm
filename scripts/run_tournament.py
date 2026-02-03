"""Run a tournament simulation."""

from mmllm.training.eval import evaluate


def main() -> None:
    results = []
    metrics = evaluate(results)
    print(metrics)


if __name__ == "__main__":
    main()
