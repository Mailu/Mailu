import os


if __name__ == "__main__":
    os.environ["DEBUG"] = "true"
    from mailu import app
    app.run()
