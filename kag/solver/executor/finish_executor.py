from kag.interface import ExecutorABC


@ExecutorABC.register("finish_executor")
class FinishExecutor(ExecutorABC):
    def schema(self):
        return {
            "name": "Finish",
            "description": "Performs no operation and is solely used to indicate that the task has been completed.",
            "parameters": {},
        }
