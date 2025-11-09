# import joblib
# import pandas as pd
# from fastapi import FastAPI, BackgroundTasks, HTTPException
# from pydantic import BaseModel
# from typing import Optional
# from config.settings import settings
# from celery import Celery
# from sqlalchemy import create_engine, text
# import logging
# import os

# # logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger("predictor-api")

# # DB engine
# engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# # Celery
# celery_app = Celery("tasks", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
# celery_app.conf.task_routes = {"tasks.retrain_task": {"queue": "retrain"}}

# # Load model
# MODEL_PATH = settings.MODEL_PATH
# model = None
# if os.path.exists(MODEL_PATH):
#     model = joblib.load(MODEL_PATH)
#     logger.info("Model loaded from %s", MODEL_PATH)
# else:
#     logger.warning("Model file not found at %s — endpoint /retrain available to create it.", MODEL_PATH)

# app = FastAPI(title="DevOps Build Failure Predictor API")

# class PredictRequest(BaseModel):
#     duration: Optional[int] = None
#     error_count: Optional[int] = None
#     commit_message: Optional[str] = None
#     # add fields you extract in feature_extractor

# @app.post("/predict")
# async def predict(req: PredictRequest):
#     global model
#     if model is None:
#         raise HTTPException(status_code=503, detail="Model not available. Trigger /retrain first.")
#     # build features consistent with training
#     x = pd.DataFrame([{
#         "duration": req.duration or 0,
#         "error_count": req.error_count or 0,
#         # add more features mapping
#     }])
#     preds_proba = model.predict_proba(x)[:, 1]  # probability of failure
#     prob = float(preds_proba[0])
#     risk = "HIGH" if prob >= settings.RISK_THRESHOLD else "LOW"
#     return {"failure_probability": prob, "risk": risk, "threshold": settings.RISK_THRESHOLD}

# @app.post("/retrain", status_code=202)
# async def retrain(background_tasks: BackgroundTasks):
#     # call Celery retrain to avoid blocking
#     celery_app.send_task("tasks.retrain_task", args=[])
#     return {"status": "retraining_started"}

# @app.get("/status")
# async def status():
#     return {"model_loaded": model is not None, "model_path": MODEL_PATH}


"""
DevOps Build Failure Predictor API
----------------------------------
This API serves a trained ML model to predict whether a CI/CD build
is likely to fail, based on metrics like build duration, error count,
and (optionally) commit message features.

Features:
- /predict → Predict failure probability using trained model
- /retrain → Trigger asynchronous retraining via Celery
- /status → Check if model is loaded and ready

Author: Honours Bhadauria
"""

import os
import joblib
import pandas as pd
import logging
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import create_engine, text
from celery import Celery
from config.settings import settings

# ------------------------------------------------------
# 🔧 Logging Configuration
# ------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("predictor-api")

# ------------------------------------------------------
# 🗃️ Database Connection
# ------------------------------------------------------
# SQLAlchemy engine for PostgreSQL
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# ------------------------------------------------------
# 🐇 Celery Task Queue
# ------------------------------------------------------
# Handles asynchronous retraining so the API remains non-blocking
celery_app = Celery("tasks", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.conf.task_routes = {"tasks.retrain_task": {"queue": "retrain"}}

# ------------------------------------------------------
# 🤖 Model Loading
# ------------------------------------------------------
MODEL_PATH = settings.MODEL_PATH
model = None

if os.path.exists(MODEL_PATH):
    model = joblib.load(MODEL_PATH)
    logger.info("✅ Model loaded successfully from %s", MODEL_PATH)
else:
    logger.warning("⚠️ Model file not found at %s — use /retrain to generate it.", MODEL_PATH)

# ------------------------------------------------------
# 🚀 FastAPI App Initialization
# ------------------------------------------------------
app = FastAPI(
    title="DevOps Build Failure Predictor API",
    description="Predict CI/CD build failures using trained ML models.",
    version="1.0.0"
)

# ------------------------------------------------------
# 📦 Request Model Schema
# ------------------------------------------------------
class PredictRequest(BaseModel):
    """
    Expected input fields for /predict endpoint.
    Each corresponds to a model feature.
    """
    duration: Optional[int] = None
    error_count: Optional[int] = None
    commit_message: Optional[str] = None  # Optional for future NLP features


# ------------------------------------------------------
# 🧠 Prediction Endpoint
# ------------------------------------------------------
@app.post("/predict")
async def predict(req: PredictRequest):
    """
    Predict build failure probability using the trained ML model.
    Returns probability, risk level, and applied threshold.
    """
    global model
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Model not available. Please trigger /retrain first."
        )

    # Build a DataFrame matching training feature order
    features = pd.DataFrame([{
        "duration": req.duration or 0,
        "error_count": req.error_count or 0,
        # Add more features if included in training (e.g., message length, keywords)
    }])

    # Get failure probability
    preds_proba = model.predict_proba(features)[:, 1]
    prob = float(preds_proba[0])

    # Compute risk category
    risk = "HIGH" if prob >= settings.RISK_THRESHOLD else "LOW"

    logger.info("Prediction made: prob=%.3f, risk=%s", prob, risk)

    return {
        "failure_probability": prob,
        "risk": risk,
        "threshold": settings.RISK_THRESHOLD
    }


# ------------------------------------------------------
# 🧩 Retraining Endpoint
# ------------------------------------------------------
@app.post("/retrain", status_code=202)
async def retrain(background_tasks: BackgroundTasks):
    """
    Trigger model retraining in the background using Celery.
    Non-blocking – returns immediately with accepted status.
    """
    celery_app.send_task("tasks.retrain_task", args=[])
    logger.info("Retraining task dispatched to Celery queue.")
    return {"status": "retraining_started"}


# ------------------------------------------------------
# 🩺 Health Check Endpoint
# ------------------------------------------------------
@app.get("/status")
async def status():
    """
    Check if model is currently loaded and its file path.
    """
    return {
        "model_loaded": model is not None,
        "model_path": MODEL_PATH,
        "database_connected": test_db_connection()
    }


# ------------------------------------------------------
# 🧱 Utility: Database Connection Check
# ------------------------------------------------------
def test_db_connection() -> bool:
    """
    Simple ping test for database connection health.
    Returns True if DB connection works, else False.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Database connection failed: %s", e)
        return False
