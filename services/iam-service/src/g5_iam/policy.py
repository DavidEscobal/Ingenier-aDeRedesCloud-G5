"""Academic RBAC + current membership + authoritative resource relation."""
from .models import Decision


def decide(db, user, query):
    def result(allowed):
        return Decision(allowed=allowed, action=query.action,
                        reason="allowed" if allowed else "not_authorized")

    if query.action == "platform.read":
        return result(True)
    if query.action in {"image.manage", "infrastructure.manage"}:
        return result(user["role"] == "admin")

    resource = None
    if query.action in {"slice.create", "template.read", "template.write"}:
        course_id = query.course_id
        if not course_id or query.resource_id:
            return result(False)
    else:
        resource = db.execute("SELECT * FROM resources WHERE id=?", (query.resource_id,)).fetchone()
        if resource is None:
            return result(False)
        if (query.action == "vm.console") != (resource["kind"] == "vm"):
            return result(False)
        course_id = resource["course_id"]
        # Never accept a client-supplied course that contradicts the stored resource.
        if query.course_id and query.course_id != course_id:
            return result(False)

    course = db.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
    if course is None:
        return result(False)
    if user["role"] == "admin":
        return result(True)
    membership = db.execute("SELECT 1 FROM memberships WHERE course_id=? AND user_id=?",
                            (course_id, user["id"])).fetchone()
    if not membership:
        return result(False)
    if user["role"] == "professor":
        if resource is None:
            return result(True)
        if resource["professor_id"] != user["id"]:
            return result(False)
        if query.action in {"slice.update", "slice.delete", "slice.start", "slice.stop"}:
            return result(bool(course["professor_can_modify"]))
        return result(True)
    if user["role"] == "student" and query.action in {"slice.read", "slice.metrics", "vm.console"}:
        assigned = db.execute("SELECT 1 FROM assignments WHERE resource_id=? AND user_id=?",
                              (resource["id"], user["id"])).fetchone()
        if not assigned:
            return result(False)
        if resource["kind"] == "vm":
            # VM console requires both slice and VM assignment.
            assigned = db.execute("SELECT 1 FROM assignments WHERE resource_id=? AND user_id=?",
                                  (resource["parent_slice_id"], user["id"])).fetchone()
        return result(bool(assigned))
    return result(False)
