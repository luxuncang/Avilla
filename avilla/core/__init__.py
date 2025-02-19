import asyncio
from typing import Any, Awaitable, Callable, Dict, Generic, List, Set, Type, Union

from graia.broadcast import Broadcast
from graia.broadcast.interfaces.dispatcher import DispatcherInterface
from loguru import logger
from rich.console import Console
from rich.logging import RichHandler
from rich.status import Status

from avilla.core.event import MessageChainDispatcher, RelationshipDispatcher
from avilla.core.launch import LaunchComponent, resolve_requirements
from avilla.core.network.service import Service
from avilla.core.protocol import BaseProtocol
from avilla.core.typing import T_Config, T_ExecMW, T_Protocol

AVILLA_ASCII_LOGO = r"""\
    _        _ _ _
   / \__   _(_) | | __ _
  / _ \ \ / / | | |/ _` |
 / ___ \ V /| | | | (_| |
/_/   \_\_/ |_|_|_|\__,_|"""


class Avilla(Generic[T_Protocol, T_Config]):
    broadcast: Broadcast
    protocol: T_Protocol
    configs: Dict[Type[T_Protocol], T_Config]
    middlewares: List[T_ExecMW]
    services: List[Service]

    launch_components: Dict[str, LaunchComponent]

    def __init__(
        self,
        broadcast: Broadcast,
        protocol: Type[T_Protocol],
        services: List[Service],
        configs: Dict,
        middlewares: List[T_ExecMW] = None,
    ):
        self.broadcast = broadcast
        self.protocol = protocol(self, configs.get(protocol))
        self.configs = configs
        self.services = services
        self.middlewares = [target_context_injector, *(middlewares or [])]  # TODO: 把那东西拿回来
        self.launch_components = {
            **({i.launch_component.id: i.launch_component for i in services}),
            self.protocol.launch_component.id: self.protocol.launch_component,
        }

        self.broadcast.dispatcher_interface.inject_global_raw(
            RelationshipDispatcher(), MessageChainDispatcher()
        )

        @self.broadcast.dispatcher_interface.inject_global_raw
        async def _(interface: DispatcherInterface):
            if interface.annotation is Avilla:
                return self
            elif interface.annotation is protocol:
                return self.protocol

    def new_launch_component(
        self,
        id: str,
        mainline: Callable[[], Awaitable[Any]],
        requirements: Set[str] = None,
        prepare: Callable[[], Awaitable[Any]] = None,
        cleanup: Callable[[], Awaitable[Any]] = None,
    ) -> LaunchComponent:
        component = LaunchComponent(id, requirements or set(), mainline, prepare, cleanup)
        self.launch_components[id] = component
        return component

    def remove_launch_component(self, id: str):
        if id not in self.launch_components:
            raise KeyError("id doesn't exist.")
        del self.launch_components[id]

    def add_service(self, service: Service):
        if service in self.services:
            raise ValueError("existed service")
        self.services.append(service)
        launch_component = service.launch_component
        self.launch_components[launch_component.id] = launch_component

    def remove_service(self, service: Service):
        if service not in self.services:
            raise ValueError("service doesn't exist.")
        self.services.remove(service)
        del self.launch_components[service.launch_component.id]

    def get_service(self, id: str) -> Union[Service, None]:
        for service in self.services:
            if service.id.avilla_uri == id:
                return service

    async def launch(self):
        console = Console()
        logger.configure(
            handlers=[
                {
                    "sink": RichHandler(console=console, markup=True),
                    "format": "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
                    "<cyan>{name}</cyan>: <cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
                }
            ]
        )
        logger.info(AVILLA_ASCII_LOGO)
        logger.info(
            "[bold]Avilla[/]: a universal asynchronous message flow solution, powered by [blue]Graia Project[/]."
        )
        for service in self.services:
            logger.info(f"using service: {service.id.avilla_uri}")
        if self.protocol.__class__.platform is not BaseProtocol.platform:
            logger.info(f"using platform: {self.protocol.__class__.platform.universal_identifier}")
        logger.info(f"launch components: {len(self.launch_components)}")
        with Status("[orange bold]preparing components...", console=console) as status:
            for component_layer in resolve_requirements(set(self.launch_components.values())):
                tasks = [
                    asyncio.create_task(component.prepare(), name=component.id)
                    for component in component_layer
                    if component.prepare
                ]
                for task in tasks:
                    task.add_done_callback(lambda t: status.update(f"{t.get_name()} prepared."))
                await asyncio.wait(tasks)
            status.update("all launch components prepared.")
        logger.info("[green bold]components prepared, switch to mainlines and block main thread.")
        try:
            await asyncio.gather(*[component.mainline() for component in self.launch_components.values()])
        finally:
            logger.info("[red bold]mainlines exited, cleanup start.")
            for component_layer in reversed(resolve_requirements(set(self.launch_components.values()))):
                tasks = [
                    asyncio.create_task(component.cleanup(), name=component.id)
                    for component in component_layer
                    if component.cleanup
                ]
                for task in tasks:
                    task.add_done_callback(lambda t: logger.info(f"{t.get_name()} cleanup finished."))
                await asyncio.wait(tasks)
            logger.info("[green bold]cleanup finished.")
            logger.warning("[red bold]exiting...")

    def launch_blocking(self):
        asyncio.get_event_loop().run_until_complete(self.launch())
