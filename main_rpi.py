import tkinter as tk

from src.platform.raspberry_pi3_production_app import (
    RaspberryPi3ProductionApp,
)


def main() -> None:
    root = tk.Tk()
    RaspberryPi3ProductionApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
