from .models import Note


def save_note(user, node, content: str) -> Note:
    """Upsert the single Note for (user, node)."""
    note, _ = Note.objects.update_or_create(
        user=user, node=node, defaults={"content": content}
    )
    return note
