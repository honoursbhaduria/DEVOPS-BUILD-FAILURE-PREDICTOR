from celery import Celery
from config.settings import settings
import logging
from model.train_model import train_and_save_model

celery = Celery("tasks", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("celery-tasks")

@celery.task(name="tasks.retrain_task", bind=True)
def retrain_task(self):
    logger.info("Retrain task started")
    try:
        model_path = train_and_save_model()
        logger.info("Model retrained and saved at %s", model_path)
        return {"status": "success", "model_path": model_path}
    except Exception as e:
        logger.exception("Retrain failed: %s", e)
        raise
