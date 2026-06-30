from train import train
from validate_model import validate
from promote_model import promote
from import_model import import_model


def run_pipeline():

    print(
        "\n========== TRAINING =========="
    )

    train_result = train()

    print(
        f"Training Result: {train_result}"
    )

    print(
        "\n========== VALIDATION =========="
    )

    validate_result = validate()

    print(
        f"Validation Result: {validate_result}"
    )

    print(
        "\n========== PROMOTION =========="
    )

    version = promote()

    print(
        f"Promoted Version: {version}"
    )

    print(
        "\n========== BENTO IMPORT =========="
    )

    import_model()

    print(
        "\n========== PIPELINE COMPLETED =========="
    )


if __name__ == "__main__":
    run_pipeline()