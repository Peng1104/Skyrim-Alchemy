"""Entry point to run the Skyrim Alchemy Optimizer API with uvicorn."""
import uvicorn


def main() -> None:
    """Start the uvicorn server for the FastAPI app."""
    uvicorn.run("app.api:app", host="0.0.0.0", port=8001)


if __name__ == "__main__":
    main()
