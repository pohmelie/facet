# x.x.x (xx-xx-xxxx)

# 0.10.0 (30-12-2023)
- add `BlockingServiceMixin` with subset of functionality from `ServiceMixin` that can be used in non-async code
- add `AsyncioServiceMixin` as an alias to `ServiceMixin`
- `ServiceMixin` is now deprecated and will be removed in 1.0.0
- add mypy type hints
- minimum python version is now 3.11

# 0.9.1 (11-01-2022)
- prevent multiple calls to `set_exception`

# 0.9.0 (10-07-2021)
- remove done tasks from tasks set

# 0.8.0 (02-07-2021)
- stop dependencies if some of them raised exception on start

# 0.7.0 (06-05-2021)
- add support for sequential, parallel and mixed starts/stops for dependencies
- add python 3.9 support

# 0.6.0 (26-12-2020)
- add dependent counter to prevent early stops

# 0.5.0 (20-12-2020)
- add python 3.6 support

# 0.4.0 (09-06-2020)
- remove unnecessary dunder calls

# 0.3.0 (02-06-2020)
- proper background tasks cancellation

# 0.2.0 (01-06-2020)
- make `add_task` plain function

# 0.1.0 (04-05-2020)
- initial implementation
