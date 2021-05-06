from asyncio import Future, Lock, Task, gather, wait, wait_for

try:
    from asyncio import create_task
except ImportError:
    from asyncio import ensure_future as create_task

__all__ = ("ServiceMixin",)
__version__ = "0.7.0"
version = tuple(map(int, __version__.split(".")))


class ServiceMixin:

    __running = False
    __tasks = ()
    __start_lock = None
    __stop_lock = None
    __exit_point = None
    __dependents = 0

    async def __wait_with_cancellation_on_fail(self, tasks):
        try:
            await gather(*tasks)
        finally:
            for task in tasks:
                task.cancel()
            await wait(tasks)

    async def __start_dependencies(self):
        self.__tasks = []
        for group in self.dependencies:
            if isinstance(group, ServiceMixin):
                group = [group]
            starts = []
            for dependency in group:
                # propagate exit point
                dependency._ServiceMixin__exit_point = self.__exit_point
                starts.append(create_task(dependency.__start()))
            if starts:
                await self.__wait_with_cancellation_on_fail(starts)

    async def __stop_dependencies(self):
        stops = []
        for task in self.__tasks:
            if not task.done():
                task.cancel()
                stops.append(task)
        if stops:
            await wait(stops)
        for group in reversed(self.dependencies):
            if isinstance(group, ServiceMixin):
                group = [group]
            stops = []
            for dependency in group:
                stops.append(create_task(dependency.__stop()))
            if stops:
                await self.__wait_with_cancellation_on_fail(stops)

    async def __start(self):
        if self.__start_lock is None:
            self.__start_lock = Lock()
        async with self.__start_lock:
            self.__dependents += 1
            if self.__running:
                return
            if self.__exit_point is None:
                self.__exit_point = Future()
            await self.__start_dependencies()
            try:
                await self.start()
            except:  # noqa
                await self.__stop_dependencies()
                raise
            else:
                self.__running = True

    async def __stop(self):
        if self.__stop_lock is None:
            self.__stop_lock = Lock()
        async with self.__stop_lock:
            self.__dependents -= 1
            if self.__dependents == 0 and self.__running:
                await wait_for(self.__stop_two_steps(), timeout=self.graceful_shutdown_timeout)

    async def __stop_two_steps(self):
        self.__running = False
        try:
            await self.stop()
        finally:
            await self.__stop_dependencies()
        self.__exit_point = None

    async def __aenter__(self):
        await self.__start()
        return self

    async def __aexit__(self, *exc_info):
        await self.__stop()

    def __task_callback(self, task):
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            self.__exit_point.set_exception(exc)

    async def wait(self):
        await self.__exit_point

    async def run(self):
        async with self:
            await self.wait()

    @property
    def graceful_shutdown_timeout(self):
        return 10

    @property
    def dependencies(self):
        return []

    @property
    def running(self) -> bool:
        return self.__running

    def add_task(self, coro) -> Task:
        task = create_task(coro)
        task.add_done_callback(self.__task_callback)
        self.__tasks.append(task)
        return task

    async def start(self):
        pass

    async def stop(self):
        pass
