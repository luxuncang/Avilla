from typing import Awaitable, Callable, List, Optional, Set


class LaunchComponent:
    id: str
    required: Set[str]

    prepare: Optional[Callable[[], Awaitable[None]]] = None
    mainline: Callable[[], Awaitable[None]]
    cleanup: Optional[Callable[[], Awaitable[None]]] = None

    def __init__(
        self,
        component_id: str,
        required: Set[str],
        mainline: Callable[[], Awaitable[None]],
        prepare: Optional[Callable[[], Awaitable[None]]] = None,
        cleanup: Optional[Callable[[], Awaitable[None]]] = None,
    ):
        self.id = component_id
        self.required = required
        self.mainline = mainline
        self.prepare = prepare
        self.cleanup = cleanup


class RequirementResolveFailed(Exception):
    pass


def resolve_requirements(components: Set[LaunchComponent]) -> List[Set[LaunchComponent]]:
    resolved = set()
    result = []
    while components:
        if layer := {
            component
            for component in components
            if component.required.issubset(resolved)
        }:
            components -= layer
            resolved.update(component.id for component in layer)
            result.append(layer)
        else:
            raise RequirementResolveFailed
    return result
