from typing import Any, Self

__all__ = ("BlockingServiceMixin",)


class BlockingServiceMixin:
    __running: bool = False
    __dependents: int = 0

    def __start_dependencies(self) -> None:
        for group in self.dependencies:
            if isinstance(group, BlockingServiceMixin):
                group = [group]
            for dependency in group:
                dependency.__start()

    def __stop_dependencies(self) -> None:
        for group in reversed(self.dependencies):
            if isinstance(group, BlockingServiceMixin):
                group = [group]
            for dependency in group:
                dependency.__stop()

    def __start(self) -> None:
        self.__dependents += 1
        if self.__running:
            return
        try:
            self.__start_dependencies()
            self.start()
        except:  # noqa
            self.__stop_dependencies()
            raise
        else:
            self.__running = True

    def __stop(self) -> None:
        self.__dependents -= 1
        if self.__dependents > 0 or not self.__running:
            return
        self.__running = False
        try:
            self.stop()
        finally:
            self.__stop_dependencies()

    def __enter__(self) -> Self:
        self.__start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.__stop()

    @property
    def dependencies(self) -> list[Self | list[Self]]:
        return []

    @property
    def running(self) -> bool:
        return self.__running

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass
