from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Union

from pydantic import BaseModel  # pylint: ignore

from ..message.chain import MessageChain
from . import Execution, Result


@dataclass
class MessageId:
    id: str  # 记得加上群组或者好友的ID(?).

    def __int__(self):
        return int(self.id)


class MessageSend(Result[MessageId], Execution):
    _auto_detect_target = True

    message: MessageChain
    reply: Optional[str] = None

    def __init__(self, message: MessageChain, reply: Optional[str] = None):
        super().__init__(message=message, reply=reply)


class MessageRevoke(Execution):
    message_id: MessageId

    def __init__(self, message_id: Union[MessageId, str]):
        super().__init__(message_id=message_id)


class MessageEdit(Execution):
    message_id: Union[MessageId, str]
    to: MessageChain

    def __init__(self, message_id: Union[MessageId, str], to: MessageChain):
        super().__init__(message_id=message_id, to=to)


class MessageFetch(Result["MessageFetchResult"], Execution):
    message_id: Union[MessageId, str]

    def __init__(self, message_id: Union[MessageId, str]):
        super().__init__(message_id=message_id)


class MessageFetchResult(BaseModel):
    time: datetime
    message_type: str
    message_id: str
    message: MessageChain

    class Config:
        extra = "ignore"


class MessageSendPrivate(MessageSend):
    pass
