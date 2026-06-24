from model import FEMModel
from view import MainView
from controller import MainController


def main():

    model = FEMModel()

    view = MainView()

    controller = MainController(
        model,
        view
    )

    view.start()


if __name__ == "__main__":
    main()