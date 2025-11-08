import joblib
import pandas as pd
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional
from config.settings import settings
from celery import Celery
from sqlalchemy import create_engine, text
import logging
import os

# logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("predictor-api")

# DB engine
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# Celery
celery_app = Celery("tasks", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.conf.task_routes = {"tasks.retrain_task": {"queue": "retrain"}}

# Load model
MODEL_PATH = settings.MODEL_PATH
model = None
if os.path.exists(MODEL_PATH):
    model = joblib.load(MODEL_PATH)
    logger.info("Model loaded from %s", MODEL_PATH)
else:
    logger.warning("Model file not found at %s — endpoint /retrain available to create it.", MODEL_PATH)

app = FastAPI(title="DevOps Build Failure Predictor API")

class PredictRequest(BaseModel):
    duration: Optional[int] = None
    error_count: Optional[int] = None
    commit_message: Optional[str] = None
    # add fields you extract in feature_extractor

@app.post("/predict")
async def predict(req: PredictRequest):
    global model
    if model is None:
        raise HTTPException(status_code=503, detail="Model not available. Trigger /retrain first.")
    # build features consistent with training
    x = pd.DataFrame([{
        "duration": req.duration or 0,
        "error_count": req.error_count or 0,
        # add more features mapping
    }])
    preds_proba = model.predict_proba(x)[:, 1]  # probability of failure
    prob = float(preds_proba[0])
    risk = "HIGH" if prob >= settings.RISK_THRESHOLD else "LOW"
    return {"failure_probability": prob, "risk": risk, "threshold": settings.RISK_THRESHOLD}

@app.post("/retrain", status_code=202)
async def retrain(background_tasks: BackgroundTasks):
    # call Celery retrain to avoid blocking
    celery_app.send_task("tasks.retrain_task", args=[])
    return {"status": "retraining_started"}

@app.get("/status")
async def status():
    return {"model_loaded": model is not None, "model_path": MODEL_PATH}
