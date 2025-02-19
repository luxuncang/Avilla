import copy
from dataclasses import dataclass
from typing import Any, Callable, Dict, Generic, List, Optional, Type, TypeVar, Union

from graia.broadcast.entities.decorator import Decorator
from graia.broadcast.entities.event import Dispatchable
from graia.broadcast.entities.exectarget import ExecTarget
from graia.broadcast.entities.signatures import Force
from graia.broadcast.exceptions import ExecutionStop
from graia.broadcast.interfaces.decorator import DecoratorInterface
from graia.broadcast.interfaces.dispatcher import DispatcherInterface

from avilla.core.builtins.profile import GroupProfile, MemberProfile
from avilla.core.contactable import Contactable
from avilla.core.message.chain import MessageChain
from avilla.core.relationship import Relationship

S = TypeVar("S")
L = TypeVar("L")

R = TypeVar("R")
P = TypeVar("P")


@dataclass
class OmegaReport:
    completed: bool
    filter: "Filter"
    result: List[Any]
    stop_at: Optional[Callable] = None


class Filter(Decorator, Generic[S, L]):
    pre = True

    alpha: ExecTarget
    omega: Callable[[OmegaReport], L]
    chains: Dict[str, List[Callable[..., Any]]]
    names: Dict[str, Callable[..., Any]]

    ignore_execution_stop: bool = False
    default_value: Optional[L] = None
    default_factory_value: Optional[Callable[[], Optional[L]]] = None
    selected_branch: str = "main"

    current_end_callback: Optional[Callable[[List[Callable[..., Any]]], Any]] = None
    _end_origin_branch: Optional[str] = None

    def __init__(
        self,
        alpha: Callable[..., S] = lambda: None,
        omega: Callable[[OmegaReport], L] = lambda x: x.result[-1],
        initial_chain: List[Callable[..., Any]] = None,
    ):
        self.alpha = ExecTarget(alpha)
        self.omega = omega
        self.chains = {"main": initial_chain or []}
        self.names = {}

    def as_param(self):
        self.pre = False
        self.ignore_execution_stop = True
        return self

    def select(self, branch: str):
        self.selected_branch = branch
        return self

    def use(self: "Filter[Any, L]", new_step: Callable[[L], R], branch: str = None) -> "Filter[L, R]":
        self.chains[branch or self.selected_branch].append(new_step)
        return self  # type: ignore

    def name(self, name: str):
        self.names[name] = self.chains[self.selected_branch][-1]
        return self

    def copy(self):
        return copy.copy(self)

    def as_boolean(self: "Filter[S, L]") -> "Filter[S, bool]":
        def wrapped_omega(report: OmegaReport) -> bool:
            return bool(self.omega(report))

        self.omega = wrapped_omega
        return self  # type: ignore

    def default(self, value: L) -> "Filter[S, L]":
        self.default_value = value
        return self

    def default_factory(self, factory: Callable[[], L]) -> "Filter[S, L]":
        self.default_factory_value = factory
        return self

    def ignore_exec_stop(self):
        self.ignore_execution_stop = True
        return self

    @classmethod
    def message(cls: "Type[Filter[MessageChain, Any]]") -> "Filter[MessageChain, Any]":
        def message_getter_alpha(message: MessageChain):
            return message

        return cls(message_getter_alpha, lambda report: report.result[-1], [])

    @classmethod
    def rs(cls: "Type[Filter[Relationship, Any]]") -> "Filter[Relationship, Any]":
        def relationship_getter_alpha(relationship: Relationship):
            return relationship

        return cls(relationship_getter_alpha, lambda report: report.result[-1], [])

    @classmethod
    def rsctx(cls: "Type[Filter[Contactable, Any]]") -> "Filter[Contactable, Any]":
        def contactable_getter_alpha(relationship: Relationship):
            return relationship.ctx

        return cls(contactable_getter_alpha, lambda report: report.result[-1], [])

    @classmethod
    def event(cls: "Type[Filter[Any, Dispatchable]]") -> "Filter[Any, Dispatchable]":
        def event_getter_alpha(dispatcher_interface: DispatcherInterface):
            return dispatcher_interface.event

        return cls(event_getter_alpha, lambda report: report.result[-1], [])

    @classmethod
    def constant(cls, value: L) -> "Filter[Any, L]":
        return cls(lambda: value, lambda report: report.result[-1], [])

    def id(self: "Filter[Any, Contactable]", *values: str) -> "Filter[Contactable, Any]":
        def id_getter_alpha(contactable: Contactable):
            if contactable.id not in values:
                raise ExecutionStop

        self.use(id_getter_alpha)
        return self

    def profile(self: "Filter[Any, Contactable]", profile_type: Type[P]) -> "Filter[P, Any]":
        def profile_getter_alpha(contactable: Contactable):
            if not isinstance(contactable.profile, profile_type):
                raise ExecutionStop
            return contactable

        self.use(profile_getter_alpha)
        return self

    def group(
        self: "Filter[Any, Union[MemberProfile, Contactable[GroupProfile]]]", *values: str
    ) -> "Filter[Union[MemberProfile, Contactable[GroupProfile]], Any]":
        def group_getter_alpha(profile_or_contactable: Union[MemberProfile, Contactable[GroupProfile]]):
            if isinstance(profile_or_contactable, MemberProfile) and profile_or_contactable.group:
                if profile_or_contactable.group.id not in values:
                    raise ExecutionStop
            elif isinstance(profile_or_contactable, Contactable) and isinstance(
                profile_or_contactable.profile, GroupProfile
            ):
                if profile_or_contactable.id not in values:
                    raise ExecutionStop
            return profile_or_contactable

        self.use(group_getter_alpha)
        return self

    def end(self):
        if self.current_end_callback is None or self._end_origin_branch is None:
            raise TypeError("this context disallow end grammer.")
        if not self.selected_branch.startswith("$:"):
            raise ValueError("invaild context")
        if self.selected_branch not in self.chains:
            raise ValueError("empty branch")
        self.current_end_callback(self.chains[self.selected_branch])
        del self.chains[self.selected_branch]
        self.current_end_callback = None
        self.selected_branch = self._end_origin_branch
        self._end_origin_branch = None
        return self

    def parallel(self):
        self._end_origin_branch = self.selected_branch
        self.selected_branch = "$:parallel"
        self.current_end_callback = self._parallel_end_callback
        self.chains["$:parallel"] = []
        return self

    def _parallel_end_callback(self, chain: List[Callable[..., Any]]):
        def gathered_wrapper(upper_result: L):
            for i in chain:
                i(upper_result)

        self.use(gathered_wrapper, self._end_origin_branch)

    async def target(self, decorator_interface: DecoratorInterface):
        alpha_result: S = await decorator_interface.dispatcher_interface.broadcast.Executor(
            self.alpha,
            decorator_interface.dispatcher_interface.execution_contexts[-1].dispatchers,
        )

        step = None
        result: List[Any] = [alpha_result]

        try:
            for step in self.chains[self.selected_branch]:
                result.append(step(result[-1]))
        except ExecutionStop:
            self.omega(OmegaReport(completed=False, filter=self, result=result, stop_at=step))
            if not self.ignore_execution_stop:
                raise
            return None
        else:
            omega_result = self.omega(OmegaReport(completed=True, filter=self, result=result, stop_at=step))
            if isinstance(omega_result, Force):
                return omega_result.target
            return (
                omega_result
                or self.default_value
                or (self.default_factory_value and self.default_factory_value())
                or None
            )
