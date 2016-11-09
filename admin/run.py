import os


if __name__ == "__main__":
    os.environ["DEBUG"] = "True"
    from mailu import app
    app.run()
