from models.audit_log import AuditLog
from models.db import db


def record(actor_id, action, entity_type, entity_id=None, detail=None, commit=True):
    entry = AuditLog(actor_id=actor_id, action=action, entity_type=entity_type,
                     entity_id=entity_id, detail=(detail or '')[:500])
    db.session.add(entry)
    if commit:
        db.session.commit()
    return entry
