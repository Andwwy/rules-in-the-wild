from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from rules_labeling_backend.db import LabelStore, Status
from rules_labeling_backend.models import (
    ClassificationItem,
    ClassificationLabel,
    ClassificationLabelIn,
    DocumentItem,
    ExtractionItem,
    ExtractionLabel,
    ExtractionLabelIn,
    MissingExtractionLabelIn,
    Stats,
)

DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "rules_pipeline" / "rules.duckdb"


def create_app(db_path: str | Path = DEFAULT_DB_PATH) -> FastAPI:
    store = LabelStore(db_path)
    app = FastAPI(title="Rules Labeling")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_store() -> LabelStore:
        return store

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/documents")
    def documents(db: LabelStore = Depends(get_store)) -> list[DocumentItem]:
        return db.documents()

    @app.get("/api/extraction-items")
    def extraction_items(
        status: Status = Query("all"),
        db: LabelStore = Depends(get_store),
    ) -> list[ExtractionItem]:
        return db.extraction_items(status)

    @app.put("/api/extraction-labels/{target_key}")
    def upsert_extraction_label(
        target_key: str,
        payload: ExtractionLabelIn,
        db: LabelStore = Depends(get_store),
    ) -> ExtractionLabel:
        try:
            return db.upsert_extraction_label(target_key, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Extraction target not found") from exc

    @app.post("/api/extraction-labels/missing")
    def add_missing_extraction_label(
        payload: MissingExtractionLabelIn,
        db: LabelStore = Depends(get_store),
    ) -> ExtractionLabel:
        return db.add_missing_extraction_label(payload)

    @app.get("/api/classification-items")
    def classification_items(
        status: Status = Query("all"),
        db: LabelStore = Depends(get_store),
    ) -> list[ClassificationItem]:
        return db.classification_items(status)

    @app.put("/api/classification-labels/{target_key}")
    def upsert_classification_label(
        target_key: str,
        payload: ClassificationLabelIn,
        db: LabelStore = Depends(get_store),
    ) -> ClassificationLabel:
        try:
            return db.upsert_classification_label(target_key, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Classification target not found") from exc

    @app.get("/api/stats")
    def stats(db: LabelStore = Depends(get_store)) -> Stats:
        return db.stats()

    return app
