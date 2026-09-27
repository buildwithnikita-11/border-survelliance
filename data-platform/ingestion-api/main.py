from fastapi import FastAPI

app = FastAPI(title="Situational Awareness Data Platform")


@app.get("/")
def root():
    return {"status": "Data platform is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}
