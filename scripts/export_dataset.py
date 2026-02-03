"""Export dataset from run logs."""

from pathlib import Path

from mmllm.training.dataset import build_dataset


def main() -> None:
    dataset = build_dataset([Path("runs")])
    print(dataset)


if __name__ == "__main__":
    main()
