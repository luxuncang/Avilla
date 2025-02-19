from typing import Optional

from graia.broadcast.entities.dispatcher import BaseDispatcher
from graia.broadcast.interfaces.dispatcher import DispatcherInterface

from avilla.core.contactable import Contactable

from ..builtins.profile import GroupProfile, StrangerProfile
from . import AvillaEvent, RelationshipDispatcher


class FriendAddRequest(AvillaEvent[StrangerProfile]):
    comment: Optional[str]
    request_id: str

    class Dispatcher(BaseDispatcher):
        mixin = [RelationshipDispatcher]

        @staticmethod
        async def catch(interface: "DispatcherInterface"):
            pass


class GroupJoinRequest(AvillaEvent[StrangerProfile]):  # 主体就是类名第一个名词.
    group: Contactable[GroupProfile]
    comment: Optional[str]
    is_invite: bool = False
    request_id: str

    class Dispatcher(BaseDispatcher):
        mixin = [RelationshipDispatcher]

        @staticmethod
        async def catch(interface: "DispatcherInterface"):
            pass
