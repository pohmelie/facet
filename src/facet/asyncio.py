from asyncio import Future, Lock, Task, create_task, gather, wait, wait_for
from collections.abc import Coroutine
from typing import Any, Self

__all__ = ("AsyncioServiceMixin",)


class AsyncioServiceMixinInternalError(Exception):
    pass


class AsyncioServiceMixin:
    __running: bool = False
    __tasks: set[Task[Any]] | None = None
    __start_lock: Lock | None = None
    __stop_lock: Lock | None = None
    __exit_point: Future[Any] | None = None
    __dependents: int = 0

    async def __wait_with_cancellation_on_fail(self, tasks: list[Task[Any]]) -> None:
        try:
            await gather(*tasks)
        finally:
            for task in tasks:
                task.cancel()
            await wait(tasks)

    def __ensure_tasks(self) -> set[Task[Any]]:
        if self.__tasks is None:
            raise AsyncioServiceMixinInternalError("tasks not initialized")
        return self.__tasks

    def __ensure_exit_point(self) -> Future[Any]:
        if self.__exit_point is None:
            raise AsyncioServiceMixinInternalError("exit point not initialized")
        return self.__exit_point

    async def __start_dependencies(self) -> None:
        self.__tasks = set()
        for group in self.dependencies:
            if isinstance(group, AsyncioServiceMixin):
                group = [group]
            starts = []
            for dependency in group:
                # propagate exit point
                setattr(dependency, "_AsyncioServiceMixin__exit_point", self.__ensure_exit_point())
                starts.append(create_task(dependency.__start()))
            if starts:
                await self.__wait_with_cancellation_on_fail(starts)

    async def __stop_dependencies(self) -> None:
        background_tasks = self.__ensure_tasks()
        for task in background_tasks:
            if not task.done():
                task.cancel()
        if background_tasks:
            await wait(background_tasks)
        for group in reversed(self.dependencies):
            if isinstance(group, AsyncioServiceMixin):
                group = [group]
            stops = []
            for dependency in group:
                stops.append(create_task(dependency.__stop()))
            if stops:
                await self.__wait_with_cancellation_on_fail(stops)

    async def __start(self) -> None:
        if self.__start_lock is None:
            self.__start_lock = Lock()
        async with self.__start_lock:
            self.__dependents += 1
            if self.__running:
                return
            if self.__exit_point is None:
                self.__exit_point = Future()
            try:
                await self.__start_dependencies()
                await self.start()
            except:  # noqa
                await self.__stop_dependencies()
                raise
            else:
                self.__running = True

    async def __stop(self) -> None:
        if self.__stop_lock is None:
            self.__stop_lock = Lock()
        async with self.__stop_lock:
            self.__dependents -= 1
            if self.__dependents == 0 and self.__running:
                await wait_for(self.__stop_two_steps(), timeout=self.graceful_shutdown_timeout)

    async def __stop_two_steps(self) -> None:
        self.__running = False
        try:
            await self.stop()
        finally:
            await self.__stop_dependencies()
        self.__exit_point = None

    async def __aenter__(self) -> Self:
        await self.__start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.__stop()

    def __task_callback(self, task: Task[Any]) -> None:
        self.__ensure_tasks().discard(task)
        if task.cancelled():
            return
        exc = task.exception()
        exit_point = self.__ensure_exit_point()
        if exc and not exit_point.done():
            exit_point.set_exception(exc)

    async def wait(self) -> None:
        await self.__ensure_exit_point()

    async def run(self) -> None:
        async with self:
            await self.wait()

    @property
    def graceful_shutdown_timeout(self) -> int:
        return 10

    @property
    def dependencies(self) -> list[Self | list[Self]]:
        return []

    @property
    def running(self) -> bool:
        return self.__running

    def add_task(self, coroutine: Coroutine[Any, Any, Any]) -> Task[Any]:
        task: Task[Any] = create_task(coroutine)
        task.add_done_callback(self.__task_callback)
        self.__ensure_tasks().add(task)
        return task

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass
