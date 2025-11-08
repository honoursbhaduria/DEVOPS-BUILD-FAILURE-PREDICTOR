"""
Train model by reading builds table from PostgreSQL and saving model to MODEL_PATH.
Returns path to saved model.
"""
import pandas as pd
from sqlalchemy import create_engine, text
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
import joblib
import os
from config.settings import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trainer")

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
MODEL_PATH = settings.MODEL_PATH
os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

def load_data_from_db(limit=None):
    q = "SELECT build_number, result, duration, timestamp, raw_log, commit_message, error_count FROM builds ORDER BY build_number"
    if limit:
        q += f" LIMIT {limit}"
    with engine.connect() as conn:
        df = pd.read_sql(text(q), conn)
    return df

def featurize(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert raw DB columns to ML-ready features.
    Update this to add text features, keyword flags, rolling metrics, etc.
    """
    df = df.copy()
    # target: 1 if failure else 0
    df = df.dropna(subset=["result"])
    df["target"] = df["result"].apply(lambda x: 1 if x.upper() in ("FAILURE","UNSTABLE") else 0)
    # example features:
    df["duration"] = df["duration"].fillna(0).astype(int)
    df["error_count"] = df["error_count"].fillna(0).astype(int)
    # you can add more: message length, keywords, time-of-day, previous build status etc.
    X = df[["duration","error_count"]]
    y = df["target"]
    return X, y

def train_and_save_model():
    logger.info("Loading data from DB")
    df = load_data_from_db()
    if df.empty:
        raise RuntimeError("No data found in builds table for training.")
    X, y = featurize(df)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    logger.info("Training model on %d samples", len(X_train))
    model = RandomForestClassifier(n_estimators=200, n_jobs=-1, random_state=42)
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    logger.info("Validation accuracy: %.4f", acc)
    joblib.dump(model, MODEL_PATH, compress=3)
    logger.info("Saved model to %s", MODEL_PATH)
    return MODEL_PATH

if __name__ == "__main__":
    train_and_save_model()
