from typing import Optional

from . import Operation


class RequestHandle(Operation):
    ...


class RequestApprove(RequestHandle):
    request_id: str

    def __init__(self, request_id: str) -> None:
        super().__init__(request_id=request_id)


class RequestDeny(RequestHandle):
    request_id: str
    reason: Optional[str] = None
    block: bool = False

    def __init__(self, request_id: str, *, reason: Optional[str] = None, block: bool = False) -> None:
        super().__init__(request_id=request_id, reason=reason, block=block)


class RequestIgnore(RequestHandle):
    request_id: str
    block: bool = False

    def __init__(self, request_id: str, *, block: bool = False) -> None:
        super().__init__(request_id=request_id, block=block)
