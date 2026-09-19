from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_scan
from ..models import Annotation, AnnotationKind, AnnotationStatus, Scan
from ..schemas import AnnotationIn, AnnotationOut

router = APIRouter(prefix="/api/scans", tags=["annotations"])


@router.get("/{scan_id}/annotations", response_model=list[AnnotationOut])
def list_annotations(
    scan: Scan = Depends(get_scan),
    db: Session = Depends(get_db),
    status: AnnotationStatus | None = Query(None),
    kind: AnnotationKind | None = Query(None),
) -> list[Annotation]:
    stmt = select(Annotation).where(Annotation.scan_id == scan.id)
    if status is not None:
        stmt = stmt.where(Annotation.status == status)
    if kind is not None:
        stmt = stmt.where(Annotation.kind == kind)
    return list(db.scalars(stmt.order_by(Annotation.updated_at.desc())))


@router.put("/{scan_id}/annotations", response_model=AnnotationOut)
def upsert_annotation(
    body: AnnotationIn,
    scan: Scan = Depends(get_scan),
    db: Session = Depends(get_db),
) -> Annotation:
    existing = db.scalar(
        select(Annotation).where(
            Annotation.scan_id == scan.id,
            Annotation.kind == body.kind,
            Annotation.ref == body.ref,
        )
    )
    if existing is None:
        existing = Annotation(scan_id=scan.id, kind=body.kind, ref=body.ref)
        db.add(existing)
    existing.status = body.status
    existing.note = body.note
    db.commit()
    db.refresh(existing)
    return existing
