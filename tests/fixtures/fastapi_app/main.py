import os

from fastapi import FastAPI

app = FastAPI()

DATABASE_URL = os.environ["DATABASE_URL"]
API_KEY = os.getenv("API_KEY")


@app.get("/")
def read_root():
    return {"Hello": "World"}
