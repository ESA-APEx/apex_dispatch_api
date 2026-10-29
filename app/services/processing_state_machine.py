"""Pure status validation; imports the existing APEx enum.

No database writes or remote requests are performed. Confirmation flags must
come from trusted integration code, never directly from a callback payload.
"""

from statemachine import State, StateMachine

from app.schemas.enum import ProcessingStatusEnum as Status


class ProcessingStateMachine(StateMachine):
    """Execution observations plus explicitly confirmed resource deletion.

    UNKNOWN describes missing knowledge, so it is handled by can_transition
    rather than represented as an execution state. FINISHED/CANCELED/FAILED
    and DELETED are final and have no outgoing transitions.
    """

    created = State(value=Status.CREATED, initial=True)
    queued = State(value=Status.QUEUED)
    running = State(value=Status.RUNNING)
    finished = State(value=Status.FINISHED, final=True)
    canceled = State(value=Status.CANCELED, final=True)
    failed = State(value=Status.FAILED, final=True)
    deleted = State(value=Status.DELETED, final=True)

    observe_queued = created.to(queued)
    observe_running = created.to(running) | queued.to(running)
    observe_finished = (
        created.to(finished) | queued.to(finished) | running.to(finished)
    )
    observe_canceled = (
        created.to(canceled) | queued.to(canceled) | running.to(canceled)
    )
    observe_failed = created.to(failed) | queued.to(failed) | running.to(failed)
    observe_deleted = (
        created.to(deleted, cond="is_deletion_confirmed")
        | queued.to(deleted, cond="is_deletion_confirmed")
        | running.to(deleted, cond="is_deletion_confirmed")
    )

    @staticmethod
    def is_deletion_confirmed(deletion_confirmed: bool = False) -> bool:
        return deletion_confirmed

    @classmethod
    def can_transition(
        cls,
        current_status: Status | str,
        new_status: Status | str,
        *,
        authoritative: bool = False,
        deletion_confirmed: bool = False,
    ) -> bool:
        """Check an update without changing a machine, model, or database.

        Accepts enum members or their serialized lowercase values. Invalid
        values raise ValueError rather than being silently treated as UNKNOWN.

        True means the update is allowed, including an idempotent no-op.
        False means preserve current_status. Incoming UNKNOWN is never allowed
        to replace a known status. Resolving a stored UNKNOWN requires a
        successful authoritative lookup for the same execution attempt.

        authoritative does not override known-state transition rules.
        deletion_confirmed is required to enter DELETED, even from UNKNOWN.
        Neither flag performs verification itself.
        """
        current = Status(current_status)
        target = Status(new_status)

        if current == target:
            return True
        if target == Status.UNKNOWN:
            return False
        if target == Status.DELETED and not deletion_confirmed:
            return False
        if current == Status.UNKNOWN:
            return authoritative

        machine = cls(start_value=current)
        event_name = f"observe_{target.value}"
        return any(
            event.id == event_name
            for event in machine.enabled_events(
                deletion_confirmed=deletion_confirmed,
            )
        )
